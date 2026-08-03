# Deterministic multi-filter evaluation

PR 5 evaluates one existing canonical candidate and its existing market snapshot against four
versioned policies. It stores only four `filter_evaluations` rows. It never copies a candidate,
snapshot, symbol, or complete source payload into the details JSON.

## Boundaries

Filtering calculations are pure Domain code. They do not know about repositories, Unit of Work,
SQLAlchemy, `.env`, wall clocks, UUID generation, KIS, Telegram, or schedulers. The Application
service loads the candidate and snapshot, calls the pure engine, assigns timestamps and evaluation
IDs through injected ports, and persists the complete batch with the existing PR 4 Unit of Work.

No strategy decision, trade intent, order, fill, position, P&L, broker, notification, collection,
scheduling, UI, CSV, or analysis behavior is included. The existing 11-table schema and Alembic
revision are unchanged.

## Input and checks

`FilterInput` contains only `Symbol`, open and last prices, previous high and low prices, optional
previous close, and optional volume. It is immutable, uses `Price`/`Decimal`, and contains no
candidate ID or database row.

Checks always run in this order:

1. `PRICE_RANGE`: `10 <= last_price <= 300`; weight 20.
2. `OPENING_CHANGE_MIN`: `(open - previous_close) / previous_close >= 0.03`; weight 20.
3. `ENTRY_CHANGE_MAX`: `(last - previous_close) / previous_close <= 0.15`; weight 20.
4. `BREAKOUT_TRIGGERED`: `last >= previous_high + 0.5 * (previous_high - previous_low)`;
   weight 30. This delegates target arithmetic to the existing PR 1 breakout function.
5. `VOLUME_PRESENT`: volume is present and positive; weight 10.

Price boundaries 10 and 300, opening change 3%, entry change 15%, and the exact breakout target are
inclusive. A missing previous close produces `NOT_EVALUABLE` for both change checks. It is distinct
from a calculated change that misses its threshold, which is `FAIL`. `PASS` earns the check weight;
`FAIL` and `NOT_EVALUABLE` earn zero. Scores are `Decimal` values from 0 through 100.

All ratio and breakout operations run in a local Decimal context with precision 38 and
`ROUND_HALF_EVEN`. They do not mutate the process-global Decimal context, use floats, or force
18-place quantization. JSON renders Decimal observations and thresholds with fixed-point strings.

## Built-in catalog

Definitions are immutable code policy, not environment configuration. All use evaluation version
`v1`, the common thresholds above, and the following stable identities:

| Filter set | Stable `FilterSetID` |
| --- | --- |
| `STRICT` | `aaad2a67-4080-5805-90d5-2b6c350b8cdd` |
| `BALANCED` | `58865908-eb8a-5089-bc66-b38b49578f84` |
| `SCORE_ONLY` | `e5f2aa3d-82e1-566a-aeb4-7313b49fc436` |
| `OBSERVATION` | `bf66c976-b971-571e-b688-d21abfacfb4d` |

Filter-set IDs are never generated at runtime. If thresholds or pass policy change, the stable ID is
retained and the evaluation version must advance to `v2`, `v3`, and so on. Existing `v1` semantics
must not be silently changed. Thresholds are deliberately excluded from `.env` so historical
results remain reproducible from version-controlled policy.

## Pass policies

- `STRICT`: all five checks are hard and must pass; minimum score 100. A hard `FAIL` or
  `NOT_EVALUABLE` fails the evaluation.
- `BALANCED`: price range and entry change are hard. All hard checks must pass and score must be at
  least 70. Opening change, breakout, and volume are soft.
- `SCORE_ONLY`: no hard checks; score must be at least 60. `NOT_EVALUABLE` affects only score.
- `OBSERVATION`: valid contract input always yields `passed=true`, including when checks fail or are
  not evaluable. The real score and checks are retained for analysis, with no blocking reasons.

The details JSON records schema version, filter-set name, mode, outcome counts, deterministic check
order, hard/soft flags, integer weights, fixed-point observations and thresholds, and categorical
blocking reasons. It does not duplicate the overall `passed` or `score` columns. Allowed blocking
codes are `HARD_CHECK_FAILED`, `HARD_CHECK_NOT_EVALUABLE`, and `SCORE_BELOW_MINIMUM`.

Serialization uses UTF-8-compatible Unicode, stable key ordering, and compact separators. Errors do
not include the payload, SQL, parameters, credentials, or raw driver representation.

## Application transaction policy

`CandidateFilterEvaluationService.evaluate_all(candidate_id)` performs this exact sequence:

1. Open one Unit of Work and load the candidate and its market snapshot.
2. Build one immutable `FilterInput`.
3. Call the injected clock exactly once.
4. Evaluate `STRICT`, `BALANCED`, `SCORE_ONLY`, and `OBSERVATION` in catalog order.
5. Generate one `FilterEvaluationID` per result and add all four rows through the existing
   repository.
6. Commit exactly once only after all four inserts succeed.

Every row in a batch has the same `evaluated_at`. A missing candidate or snapshot raises a safe
application error. A duplicate is not treated as success and is not read back, overwritten, deleted,
or upserted. It becomes `FilterEvaluationConflictError`; the entire current batch rolls back. A
future re-evaluation therefore requires an explicit version bump or a separately designed policy.

All write verification runs only in guarded `auto_trading_v2_test_*` temporary databases. The
development diagnostic remains read-only:

```powershell
python scripts/check_persistence.py
```

Strategy decisions are intentionally the next downstream stage and are not part of this PR.
