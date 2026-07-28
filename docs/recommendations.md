# Canonical Recommendation contract

## Boundary

A Recommendation is one immutable recommendation or non-recommendation for exactly one
FeatureSnapshot. It is separate from Candidate, FilterEvaluation, StrategyDecision, TradeIntent,
orders, fills, positions, and outcomes. P1 stores validated caller-supplied results; it does not run a
model, rank symbols, size an amount, notify a user, or place an order.

## Disposition and plan

`RECOMMEND` and `CONDITIONAL` are actionable. They require a USD long plan containing positive entry
range, target and stop prices, 1–5 expected holding trading days, three Decimal probabilities,
positive expected-value rate, positive reward/risk ratio, Decimal confidence, and an aware UTC
`valid_until`. Price order is:

```text
stop < entry low <= entry high < target
```

Each probability and confidence is in `[0, 1]`; target plus stop probability is at most 1.
`valid_until` is later than `generated_at`, and holding days cannot exceed the source FeatureSnapshot
horizon.

`WATCH`, `NO_RECOMMENDATION`, `DATA_INSUFFICIENT`, and `MARKET_RISK` are non-actionable. They have no
plan object and store every plan column as SQL `NULL`, never placeholder zeroes.

## Canonical codes

Reason, risk, and invalidation codes match `^[A-Z][A-Z0-9_]{0,63}$`, reject duplicates, and are sorted
before compact JSON array storage. Every result has a reason. Actionable results and `MARKET_RISK`
have a risk. Actionable results have at least one invalidation code; non-actionable results have none.
Errors never render the complete code collection or source payload.

## FeatureSnapshot validation

The application reads the source before a Recommendation write. It requires:

- an existing, matching FeatureSnapshot ID;
- `generated_at >= FeatureSnapshot.as_of`;
- READY quality for actionable dispositions;
- plan holding days no greater than the FeatureSnapshot horizon.

Symbol, feature values, provenance, quality reasons, and source cutoff are not copied into the
Recommendation.

## Identity, digest, and idempotency

The semantic key is `recommendation:v1:` plus 64 lowercase SHA-256 characters over FeatureSnapshot
ID, generator code, and generator version. The content digest hashes only disposition, plan or
`null`, and canonical reason/risk/invalidation codes. IDs and timestamps affect neither hash.

Same identity and content returns `ALREADY_EXISTS` without a new ID, insert, or commit. Same identity
with different content is a sanitized conflict. A unique race rolls back and checks the key in a
fresh Unit of Work; it returns the matching record, reports conflict, or raises a safe race-resolution
error when no row is visible. No update, overwrite, delete/reinsert, or upsert path exists.

## Persistence

`trading.recommendations` has an immutable insert/read repository with `add`, `get_by_id`,
`get_by_recommendation_key`, and `list_by_feature_snapshot_id`. SQLAlchemy and DotNet use the same
Core statements and mapping in caller-owned transactions. Migration `0005_recommendations` creates
only this table and downgrades only this table.
