# Position StrategyDecision canonical source

## Version-pinned persistence boundary

Position decisions use two immutable canonical sources:

```text
OPEN PaperPosition(position_id, version)
  -> PositionEvent(position_id, sequence_no)

canonical MarketSnapshot
  -> StrategyDecision(position_id, position_version, market_snapshot_id)
```

`paper_positions` is mutable current state. A position decision therefore stores
`position_version` as well as `position_id`; the composite reference resolves the exact
`position_events` row whose `sequence_no` produced that version. The decision's quantity,
average cost, realized P&L, and event time can consequently be reconstructed after the current
position changes.

A candidate decision remains linked to its snapshot through `Candidate.market_snapshot_id`.
Its `strategy_decisions.market_snapshot_id` and `position_version` are always `NULL`. A position
decision has no candidate or filter evaluation and stores `position_id`, `position_version`, and
`market_snapshot_id` directly.

## Database defenses

Revision `0002_position_snapshot` added the direct snapshot source. Revision
`0003_position_decision_version` adds the nullable `position_version` column, shape and positive
value checks, lookup index, and this `ON DELETE NO ACTION` composite FK:

```text
strategy_decisions(position_id, position_version)
  -> position_events(position_id, sequence_no)
```

The referenced pair is protected by `uq_position_events_position_sequence`. The source shape is:

```text
candidate decision:
  candidate_id IS NOT NULL
  position_id IS NULL
  position_version IS NULL
  market_snapshot_id IS NULL

position decision:
  candidate_id IS NULL
  position_id IS NOT NULL
  position_version IS NOT NULL AND position_version > 0
  market_snapshot_id IS NOT NULL
  filter_evaluation_id IS NULL
```

The filtered unique index `ix_strategy_decisions_position_snapshot_unique` still permits at most
one row for `(position_id, market_snapshot_id, strategy_id, strategy_version)`. Position version
is deliberately not part of semantic identity: reevaluating the same position and snapshot cannot
silently create a second decision after the position changes. The global `decision_key` unique
constraint remains a second defense.

The migration does not guess a version for existing position decisions. Upgrade is blocked with a
sanitized error if any such row exists, so an explicit data-specific backfill can be planned.
Existing candidate decisions remain valid with `position_version = NULL`.

## Contract and Repository

`NewPositionStrategyDecision` and `StoredPositionStrategyDecision` use typed IDs, UTC-aware
timestamps, immutable normalized reason-code tuples, and require an integer `position_version`
greater than zero; `bool` is rejected. Position actions are limited to `EXIT_LONG` and `SKIP`.

The existing StrategyDecision Repository provides `add_position`, `get_position`, and
`get_by_position_snapshot_strategy`. PositionEvent Repository adds
`get_by_position_sequence(position_id, sequence_no)` for exact version reconstruction.
Repositories do not begin, commit, or roll back transactions, and the Unit of Work still exposes
exactly nine Repository instances.

## Deterministic EXIT_LONG evaluation

`PositionExitDecisionService.decide(position_id, market_snapshot_id)` resolves the current
PaperPosition, its exact version event, the event's Fill -> Order -> TradeIntent -> candidate
StrategyDecision chain, and the requested MarketSnapshot. Before writing, it validates:

- the position is open, positive, and not closed;
- the exact PositionEvent matches version, quantity, average cost, realized P&L, and event type;
- the entry source is an eligible `ENTER_LONG` strategy and matches position identity;
- position currency is USD and the snapshot symbol matches;
- snapshot time is not before the position or event;
- snapshot age is at most five minutes;
- future clock skew is at most 30 seconds.

Invalid or stale sources create no `SKIP` row. They are data-quality errors.

The service reads Clock exactly once, evaluates pure Decimal policy, stores the evaluated
`position_version`, and commits only the new decision. Repeating the same semantic tuple returns
the existing row as `ALREADY_DECIDED`; a duplicate race is resolved in a fresh Unit of Work and is
accepted only when the exact tuple exists.

## Deferred SELL boundary

An `EXIT_LONG` decision does not create a SELL TradeIntent in this slice. The future SELL
conversion must revalidate that the position is still open, its current version equals
`decision.position_version`, and its current quantity equals the pinned PositionEvent quantity.
It must reject stale decisions and over-selling rather than updating the immutable decision.

This slice also excludes SELL PaperOrder/PaperFill, Position reduction or closure, realized or
unrealized P&L, EquitySnapshot, trading-event writing, scheduling, Telegram, KIS, UI, and real
orders.
