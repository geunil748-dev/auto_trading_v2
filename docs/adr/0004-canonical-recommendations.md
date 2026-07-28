# ADR 0004: Canonical Recommendations

## Status

Accepted for Prediction P1.

## Context

The product output is an investment recommendation that a user may act on outside the system. A
Recommendation must preserve what the system recommended or declined to recommend at a reproducible
Point-in-Time cutoff. Existing StrategyDecision and TradeIntent records represent historical shadow
simulation and execution concerns, so reusing either would couple the official user output to an
order workflow.

## Decision

- A Recommendation is an immutable aggregate and the canonical user-facing output.
- Every Recommendation references exactly one existing FeatureSnapshot with `ON DELETE NO ACTION`.
- `RECOMMEND` and `CONDITIONAL` require a complete actionable plan.
- `WATCH`, `NO_RECOMMENDATION`, `DATA_INSUFFICIENT`, and `MARKET_RISK` are non-actionable and persist
  every plan column as `NULL`.
- Semantic identity contains only FeatureSnapshot ID and generator code/version.
- Content digest contains disposition, plan or no plan, and canonical reason/risk/invalidation codes.
- Exact retry returns the existing record; different content for the same identity is a conflict.
- FeatureSnapshot source validation and Recommendation write occur in one Unit of Work.
- SQLAlchemy and DotNet reuse the same SQLAlchemy Core statements and canonical row mapping.
- Recommendation creation never creates or calls TradeIntent, order, fill, position, broker, KIS,
  or Telegram behavior.

## Consequences

Migration `0005_recommendations` adds only `trading.recommendations`; the canonical table count
becomes 13. Stored Recommendations cannot be updated, deleted, or upserted through the repository.
P1 validates caller-supplied content but does not calculate a recommendation.

RecommendationRun, cross-symbol ranking, amount sizing, external data ingestion, notification,
UserAction, Outcome, and optional paper simulation linkage remain later slices.
