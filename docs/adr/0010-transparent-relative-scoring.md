# ADR 0010: Transparent cross-sectional relative scoring

- Status: Accepted
- Scoring policy: `US_EQUITY_DAILY_TECHNICAL_RELATIVE_SCORE/v1`
- Ranking policy: `QUALITY_TIERED_CROSS_SECTIONAL_PERCENTILE/v1`
- Source: one persisted P3 `US_EQUITY_DAILY_FEATURE_BATCH/v1` run
- Migration: `0008_daily_feature_scoring`

## Context

The prediction pivot needs an inspectable same-universe ordering before future-outcome observation
and probability calibration exist. Reusing Recommendation probability or expected-value fields
would misstate what current technical features can support and would weaken the existing actionable
READY gate.

## Decision

P4A validates the exact P3 and FeatureSnapshot contracts, parses finite canonical Decimal strings,
and calculates ascending midrank percentiles with a local precision-38, half-even Decimal context.
Five price components use READY and supported volume-related DEGRADED items. The volume component
uses READY items only. Active weights are normalized, so a DEGRADED item has no synthetic zero or
volume penalty.

Ranking first separates READY from DEGRADED, then orders by overall score, momentum, trend, MIC,
and symbol. Ranks are unique consecutive integers. Every P3 item remains in the immutable audit
aggregate even when it cannot be scored.

The score means only relative technical position within the source P3 run and universe. It is not a
probability, expected return, win rate, confidence measure, recommendation, or trading instruction.
P4A does not call providers, build bars or FeatureSnapshots, change the Recommendation domain or
READY gate, or create Recommendation, TradeIntent, broker, order, notification, or scheduler work.

## Persistence and consequences

Migration 0008 adds `daily_feature_scoring_runs` and `daily_feature_scoring_items`, increasing the
canonical table count from 17 to 19. The aggregate uses insert-only SQLAlchemy/DotNet repositories,
one Unit of Work commit, deterministic identity/content digests, exact retry, and safe unique-race
resolution. The persisted six-decimal representation is the only quantization boundary.

P4B may add prospective outcome observation and walk-forward probability calibration without
reinterpreting this score. Actionable Recommendation generation remains a separate P4C concern.
