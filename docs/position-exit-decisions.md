# Version-pinned deterministic EXIT_LONG decisions

## Policy

The official policy is `FIXED_POSITION_EXIT/v1`. It applies uniformly to USD positions opened by
`STRICT_ENTRY v1`, `BALANCED_ENTRY v1`, or `SCORE_ONLY_ENTRY v1`.
`OBSERVATION_ONLY` is ineligible.

The canonical inputs are:

- current price: `MarketSnapshot.last_price`;
- cost basis: exact-version `PositionEvent.average_cost_after`;
- holding start: `PaperPosition.opened_at`;
- evaluation time: `MarketSnapshot.observed_at`.

Return rate is calculated without intermediate quantization:

```text
(last_price - average_cost_after) / average_cost_after
```

The inclusive triggers are:

| Trigger | Condition |
| --- | --- |
| stop loss | return rate `<= -0.05` |
| take profit | return rate `>= 0.10` |
| time exit | elapsed time `>= 6 hours` |

If any trigger is active, action is `EXIT_LONG`. Trigger reason codes are emitted in deterministic
order: `STOP_LOSS_TRIGGERED`, `TAKE_PROFIT_TRIGGERED`, `TIME_EXIT_TRIGGERED`, followed by
`EXIT_LONG_ALLOWED`. If no trigger is active, action is `SKIP` with
`EXIT_CONDITIONS_NOT_MET`, `POSITION_HOLD`.

## Freshness and source validation

The service loads the current position, its exact PositionEvent version, the event's canonical BUY
Fill chain, and the requested snapshot. It rejects rather than storing a SKIP decision when:

- the position is missing, closed, empty, or otherwise not OPEN;
- the PositionEvent does not exactly match version, quantity, average cost, realized P&L, or type;
- the Fill, Order, TradeIntent, entry StrategyDecision chain is missing or inconsistent;
- strategy identity/version is unsupported or is not an `ENTER_LONG` source;
- currency is not USD or symbol does not match;
- the snapshot predates the position/event;
- snapshot age exceeds five minutes;
- snapshot time is more than 30 seconds in the future.

The exact five-minute age and exact 30-second future boundary are accepted. Clock is read exactly
once and normalized to UTC.

## Version pin and idempotency

Every stored position decision contains:

```text
position_id
position_version
market_snapshot_id
strategy_id
strategy_version
action
reason_codes
decided_at
```

The composite FK from `(position_id, position_version)` to
`position_events(position_id, sequence_no)` makes the evaluated position state reproducible.

Semantic identity remains:

```text
position_id + market_snapshot_id + strategy_id + strategy_version
```

The deterministic decision key and filtered unique index enforce it. A normal repeat returns
`ALREADY_DECIDED` without changing DecisionID or `decided_at`. A duplicate race rolls back and
uses a fresh Unit of Work; only an exact semantic match is accepted as already decided. Unrelated
unique, FK, or CHECK failures remain persistence errors.

## Transaction and mutation boundary

Source loading, validation, pure policy evaluation, decision insertion, and commit use one Unit of
Work. Repositories do not commit. Failures leave the decision count unchanged and never mutate
PaperPosition, PositionEvent, MarketSnapshot, PaperFill, PaperOrder, TradeIntent, or an existing
StrategyDecision.

## Deferred SELL conversion

`EXIT_LONG` is an immutable decision, not a SELL request. A future SELL TradeIntent conversion must
revalidate the current OPEN position against `decision.position_version` and the pinned event
quantity. A stale decision must not be used to sell a newer or different position quantity.

This PR does not implement SELL TradeIntent, SELL PaperOrder/PaperFill, position reduction or
closure, realized/unrealized P&L, EquitySnapshot, TradingEvent, scheduler, Telegram, KIS, market
calendar, trailing stop, partial take profit, UI, or real orders.
