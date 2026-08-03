# ADR 0011: Prospective forward outcome observation

- Status: Accepted
- Scope: Prediction P4B.1
- Migration: `0009_daily_feature_outcomes`

## Decision

Persist raw realized 1–5 trading-day price-path outcomes as immutable revisions linked to P4A, P3,
and the source FeatureSnapshot. Use FeatureSnapshot `last_close` as the reference and only existing
canonical DailyMarketBars selected Point-in-Time at the observation cutoff. Store terminal return,
MFE, MAE, safe ordered provenance, and an explicit `PROSPECTIVE` or `RETROSPECTIVE_REPLAY` mode.

Observation commands are immutable audit aggregates with exact-retry identity. Corrected provider
bar paths create new outcome keys through a path-revision digest; existing outcomes are never
updated. SQLAlchemy and DotNet share the same SQLAlchemy Core statements and mapping contract.

## Boundaries and consequences

P4B.1 performs no provider call and writes no DailyMarketBar, FeatureSnapshot, scoring row,
Recommendation, TradeIntent, or order. It defines no probability, label, calibration, expected
value, barrier, entry, target, or stop. The static official calendar covers only 2026, so an outcome
requiring a 2027 session remains explicitly out of coverage. P4B.2 may derive versioned labels and
walk-forward calibration from these raw revisions; P4C may later consume calibrated evidence.
