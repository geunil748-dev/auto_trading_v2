# Canonical BUY Fill Position Projector

## Canonical boundary

`PaperFill` is the only execution fact accepted by the Position Projector. The public operation
accepts one `fill_id`; callers cannot provide symbol, strategy, currency, quantity, price, position
quantity, or average price. The projector resolves those values through:

```text
PaperFill
  → PaperOrder
  → TradeIntent
  → StrategyDecision
  → Candidate
  → MarketSnapshot
```

Only the Position Projector creates or changes `paper_positions`. Other services must not maintain
parallel position quantities or average-cost state.

## OPENED and INCREASED

The projector currently supports canonical BUY fills only. The first BUY fill for an
`OPEN / strategy / symbol / currency` key creates one PaperPosition and one `OPENED` PositionEvent.
The position starts with the fill quantity and price, zero realized P&L, the fill execution time for
both `opened_at` and `updated_at`, and version one. The event uses sequence one.

A later BUY fill for the same key appends an `INCREASED` event and updates the existing position.
`opened_at`, OPEN status, and realized P&L are preserved. `updated_at` becomes the current fill time,
and both event sequence and resulting position version advance by exactly one.

## Weighted average

The new average entry price is calculated with Decimal values only:

```text
new_quantity = old_quantity + fill_quantity

new_average_price =
    (
        old_quantity × old_average_price
        + fill_quantity × fill_price
    )
    ÷ new_quantity
```

Intermediate multiplication, addition, and division are not quantized. The final value is stored at
the canonical scale of 18 decimal places with `ROUND_HALF_EVEN`. Fee is zero in the PR9 fill policy,
so no fee adjustment is added.

## Fill idempotency

Before writing, the projector looks up `position_events.fill_id`. An existing event returns
`ALREADY_APPLIED` without changing position quantity, average price, version, or event count.

The database remains the final race defense:

- `uq_position_events_fill_id` permits at most one event per fill;
- `uq_position_events_position_sequence` protects event order;
- `ix_paper_positions_open_unique` permits one OPEN position per strategy, symbol, and currency.

If a duplicate race occurs, the failed transaction is rolled back and the fill event is checked
again in a fresh Unit of Work. Only an event that actually exists for that fill becomes
`ALREADY_APPLIED`; unrelated unique or integrity failures are not treated as success.

## Optimistic version and transactions

An existing position update uses all of:

```text
position_id = expected position
status = OPEN
version = expected version
```

Success increments version by exactly one. A zero-row update is a missing-position or optimistic
concurrency error. No automatic merge or retry occurs inside the Repository.

For a new position, PaperPosition insert and `OPENED` event insert share one transaction. For an
existing position, `INCREASED` event insert and optimistic PaperPosition update share one
transaction. A failed event, position insert, position update, or commit rolls back both sides.
Repositories never begin or commit their own transaction. The Unit of Work exposes nine
repositories on the same connection and root transaction.

## Deliberate limits and next step

This PR does not process SELL fills, reduce or close positions, calculate realized or unrealized
P&L, write EquitySnapshots or trading events, call KIS, schedule projection, or send Telegram
notifications. PR11 adds only the persistence prerequisite that links a position decision directly
to its canonical MarketSnapshot. The following position-focused PR should define the actual
`EXIT_LONG` decision policy. SELL execution and closing projection remain separate boundaries.
