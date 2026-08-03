# ADR 0014: Explicit price-only daily technical FeatureSet v2

## Status

Accepted for Draft review.

## Context

`US_EQUITY_DAILY_TECHNICAL/v1` contains 14 price features and three volume features. Twelve Data
provides complete split-adjusted OHLC history, but adjusted-volume equivalence is not proven, so the
canonical adapter stores volume as null. v1 correctly reports that input as
`DEGRADED / VOLUME_DATA_INCOMPLETE`; changing v1 would invalidate immutable identities and evidence.

## Decision

Add explicit `US_EQUITY_DAILY_TECHNICAL/v2` and `US_EQUITY_DAILY_FEATURE_BATCH/v2` policies. v2
uses the same 21 completed split-adjusted bars, Point-in-Time cutoff, provenance, local Decimal
context, and exact 14 price calculations as v1. Its payload contains only those 14 values plus
`adjustment_basis` and `completed_bar_count`; the three v1 volume keys are absent, never null.

Twenty-one valid price bars yield `READY` regardless of null, zero, or complete volume. Fewer than
21 yield `DATA_INSUFFICIENT` without a snapshot write. v1 remains the default and unchanged, and
every v2 caller must select it explicitly. The Training Readiness Audit may classify a persisted v1
snapshot as counterfactually eligible only when exact policy, price values, metadata, and
volume-only quality reasons prove that conclusion.

## Consequences

v2 `READY` is data completeness, not profitability. This decision adds no model, probability,
score, label, Recommendation, TradeIntent, provider fallback, or order. It uses the existing
FeatureSnapshot and P3 tables, so there is no migration: Alembic head remains
`0010_outcome_labels_calibration_dataset`, canonical tables remain 25, and UoW repositories remain
19. Price-only and verified-volume-enhanced models can be compared later.

The paused P4B.2B experiment is not resumed and is not the next slice. Recommended next work is a
multi-year calendar with historical backfill, or a separately reviewed price-only relative scoring
v2 policy.
