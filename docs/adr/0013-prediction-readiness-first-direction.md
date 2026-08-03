# ADR 0013: Prediction readiness-first direction

Status: Accepted

## Context

The final product goal is unchanged: an overseas-equity investment decision-support system that
collects daily data, evaluates executable opportunities, communicates qualified recommendations,
and leaves execution to the user. PREDICTION, VIRTUAL, and ACTUAL evidence remain separate.

The P4B.2B walk-forward sigmoid implementation reached unit and scripted MSSQL validation but was
paused before its full integration suite ran. It is `PAUSED_NOT_ABANDONED`; its worktree and
secret-safe source backup are preserved outside this branch. The pause is not a code-failure
finding and the remaining one-time P4B.2B full-integration authorization is not reused here.

P4B.2A can persist a READY-only dataset whose provider is Twelve Data. Twelve Data volume is not
part of the verified canonical contract, so the READY-only filter may leave zero usable samples.
Fitting a model before measuring that risk would answer an unknown or empty research question.

The current label, `forward_close_return > 0`, is now named
`LEGACY_POSITIVE_CLOSE_RESEARCH_LABEL` in product documentation. It is not executable-trade
success, net profitability, next-open-entry success, target-first probability, stop avoidance,
execution probability, Recommendation confidence, or expected value. P4A overall score is a
within-run relative rank; it is not a probability, expected return, absolute quality measure, or
cross-date comparable score.

## Decision

No probability model is allowed before deterministic training-readiness evidence. Development
order is:

1. executable MVP trading contract;
2. Training Readiness Audit;
3. data-quality correction;
4. multi-year calendar and historical backfill;
5. daily prospective collection;
6. execution-aligned OutcomePolicy v2;
7. cost-adjusted LabelPolicy v2;
8. simple baseline comparison;
9. probability model;
10. Recommendation Generator;
11. entry/target/stop policy;
12. Telegram and UserAction;
13. fixed-universe expansion;
14. rule-based dynamic universe.

The audit is read-only and targets explicit persisted P4B.2A dataset IDs. It separates data
availability, legacy positive-close calibration readiness, and executable-trade model readiness.
It reports unknown lineage as `NOT_DERIVABLE_FROM_CURRENT_SCHEMA`, never as zero.

The choice between `PRICE_ONLY_FEATURESET_V2` and a verified-volume provider remains undecided.
The audit's READY/DEGRADED, volume, session, symbol, provider, and exclusion evidence must guide
that decision. A counterfactual claim that a sample would be READY without volume is not currently
canonical and must remain explicitly not derivable.

Prospective and retrospective evidence remain separate. Model replacement, when it becomes
permitted, is periodic and independently gated; it is never automatic per trade.

## Consequences

This slice creates no model, artifact, probability, expected value, Recommendation, market-data
row, outcome, label, dataset, Telegram message, TradeIntent, or order. It adds no migration or
table and leaves the canonical table count at 25 with Alembic head
`0010_outcome_labels_calibration_dataset`.

`RECOMMEND`, `WATCH`, `NO_RECOMMENDATION`, `MARKET_RISK`, and `DATA_INSUFFICIENT` are all normal
future product outputs. No recommendation is valid and expected when evidence is inadequate.
