# ADR 0009: Canonical multi-symbol daily feature pipeline

- Status: Accepted
- Pipeline: `US_EQUITY_DAILY_FEATURE_BATCH/v1`
- Feature set: `US_EQUITY_DAILY_TECHNICAL/v1`
- Migration: `0007_multi_symbol_feature_pipeline`

## Context

P2 produced deterministic Point-in-Time daily technical features for one symbol. The prediction
pivot needs a reproducible multi-symbol input set before scoring or recommendations can be designed.
A failure for one listing must not erase successful canonical bars or features for other listings,
and a retry must not spend another provider credit.

## Decision

The caller supplies a versioned universe containing 1 to 100 `(symbol, listing MIC)` members. The
system freezes canonical MIC-then-symbol order in an immutable UniverseSnapshot. `XNGS`, `XNGM`,
`XNCM`, `XNYS`, and `XASE` are supported; `XNAS` is not converted.

One pipeline run uses one provider, completed session, calendar version, split-adjustment basis,
feature set/version, horizon, and normalized `as_of`. Twelve Data is
`PRIMARY_FEATURE_SOURCE`; Alpaca IEX is `VALIDATION_ONLY`. Execution is sequential with no fallback,
provider blending, or parallel calls. A preflight must prove the daily budget can cover the maximum
estimated cost. The provider limiter may wait for minute capacity.

Symbol-specific no-data, insufficient-data, and business errors are recorded and processing
continues. Authentication, disabled/missing configuration, access, schema drift, calendar coverage,
and persistence failures abort remaining items. Three consecutive transient failures open the v1
circuit. Successful bar and FeatureSnapshot transactions from earlier symbols are retained.

The run key is computed before execution. Exact retry returns the existing immutable run and items
without IDs, network, bar writes, or feature builds. Final run and item records are inserted in one
Unit of Work. Migration 0007 adds exactly three tables, increasing the canonical count from 14 to 17.
Migration 0007 widens Alembic's non-canonical `dbo.alembic_version.version_num` bookkeeping column
from `VARCHAR(32)` to `VARCHAR(64)` so an existing 0006 database can store the frozen P3 revision
identifier without truncation. Downgrade retains the compatible width.

## Consequences

- Per-symbol results and overall run status are auditable and deterministic.
- Free-provider credits are protected by preflight, sequential execution, and exact retry.
- SQLAlchemy and DotNet use the same repositories, statements, mappings, and transaction contract.
- Universe membership is not a score or rank.
- P3 creates no Recommendation, ranking, TradeIntent, broker request, order, scheduler, or ML model.
- P4 may consume these FeatureSnapshots for baseline scoring and Recommendation generation.
