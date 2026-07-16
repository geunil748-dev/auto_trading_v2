# Position StrategyDecision canonical source

## Persistence boundary

PR11 prepares the persistence prerequisite for a future position exit policy:

```text
OPEN PaperPosition
  + canonical MarketSnapshot
  → position-based StrategyDecision
```

A candidate decision remains linked to its MarketSnapshot through `Candidate.market_snapshot_id`.
Its `strategy_decisions.market_snapshot_id` is always `NULL`. A position decision has no candidate
or filter evaluation and stores both `position_id` and `market_snapshot_id` directly.
`trading_events` may later reference the same records for a unified timeline, but it is not the
source of truth for this relationship.

## Database defenses

Revision `0002_position_snapshot` adds a nullable `market_snapshot_id` column and an `ON DELETE NO
ACTION` FK to `trading.market_snapshots`. The source shape is:

```text
candidate decision:
  candidate_id IS NOT NULL
  position_id IS NULL
  market_snapshot_id IS NULL

position decision:
  candidate_id IS NULL
  position_id IS NOT NULL
  market_snapshot_id IS NOT NULL
  filter_evaluation_id IS NULL
```

The filtered unique index `ix_strategy_decisions_position_snapshot_unique` permits at most one row
for `(position_id, market_snapshot_id, strategy_id, strategy_version)` when `position_id` is not
NULL. The existing global `decision_key` unique constraint remains a second defense.

The deterministic position key is:

```text
position:{position_id}|snapshot:{market_snapshot_id}|strategy:{strategy_id}|version:{version}
```

It is never truncated. Inputs that would exceed `VARCHAR(160)` are rejected.

## Contract and Repository

`NewPositionStrategyDecision` and `StoredPositionStrategyDecision` use typed IDs, UTC-aware
timestamps, immutable tuples of normalized reason codes, and allow only `EXIT_LONG` or `SKIP`.
There is no application service that creates these decisions in this PR.

The existing StrategyDecision Repository adds `add_position`, `get_position`, and
`get_by_position_snapshot_strategy`. Candidate and position mappers reject the other source shape.
Repositories do not begin, commit, or roll back transactions, and the Unit of Work still exposes
exactly nine Repository instances.

## Deferred application policy

The next EXIT_LONG policy must validate at least:

- the Position is `OPEN`;
- Position and MarketSnapshot symbols match;
- the snapshot observation is not before the position's accepted evaluation time;
- the Position strategy matches the decision strategy;
- price currency and Position currency follow an explicit policy;
- stale snapshots are rejected;
- reevaluating the same snapshot returns an idempotent result.

This PR does not implement take-profit, stop-loss, time-exit, EXIT_LONG orchestration, SELL
TradeIntent, SELL PaperOrder/PaperFill, Position reduction or closure, realized/unrealized P&L,
EquitySnapshot, trading-event writing, scheduling, Telegram, KIS, UI, or real orders.
