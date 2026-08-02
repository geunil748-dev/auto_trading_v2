# Transparent relative scoring

P4A turns one eligible persisted P3 run into an immutable scoring run. It reads no external API,
writes no DailyMarketBar or FeatureSnapshot, and creates no Recommendation, TradeIntent, or order.
Its 0-to-100 values compare technical features only inside the same P3 universe/run. They are not
probabilities, expected returns, confidence values, or comparable across different runs.

## Fixed source and feature contract

The only supported source is `US_EQUITY_DAILY_FEATURE_BATCH/v1` using
`TWELVE_DATA_TIME_SERIES`, `SPLIT_ADJUSTED`, and `US_EQUITY_DAILY_TECHNICAL/v1`. COMPLETED,
COMPLETED_WITH_WARNINGS, and COMPLETED_WITH_PARTIAL_FAILURES runs are eligible. READY snapshots must
have all volume features. DEGRADED snapshots are accepted only for `VOLUME_DATA_INCOMPLETE` or
`VOLUME_DATA_UNUSABLE` and keep the three volume features null. Other source items remain
unscorable audit records.

All 17 Decimal-valued features are finite canonical Decimal strings; Python float, exponent syntax,
NaN/Infinity, missing keys, and extra keys are rejected for that item. The reference fields are
`last_close`, `completed_bar_count=21`, and `adjustment_basis=SPLIT_ADJUSTED`.

## Percentiles and components

For each feature, ascending midrank percentile is
`(average one-based rank - 1) / (N - 1)`; a single-item population receives `0.5`. Ties share the
average rank. Calculations use Decimal precision 38 with `ROUND_HALF_EVEN` in a local context and
do not quantize intermediate values.

- Momentum: mean percentiles of 1-, 5-, and 20-day return.
- Trend: mean percentiles of close versus SMA5, SMA10, and SMA20.
- Breakout: mean percentiles of distance from the prior 20-day high and low.
- Price action: mean percentiles of latest gap and intraday return.
- Stability: mean of one minus the latest range, 20-day realized volatility, and ATR14 percentiles.
- Volume: READY-only mean percentiles of the two volume ratios and 20-day average dollar volume.

Each component is multiplied by 100. READY overall weights are 25/25/20/10/10/10 in the order
above. DEGRADED excludes volume and normalizes the active 25/25/20/10/10 weights; null volume is
never treated as zero.

## Ranking, audit, and retry

Scored items sort READY before DEGRADED, then overall, momentum, and trend descending, then MIC and
symbol ascending. Rank starts at 1 and is unique and consecutive; P3 ordinal remains unchanged.
Unscorable items have null scores/rank and a safe reason code.

Run identity contains only source P3 run ID and fixed policy codes/versions. Content digest covers
status/counts and canonical ordinal item results but excludes IDs, key, and timestamps. Exact retry
returns the stored aggregate without feature reads, calculation, ID generation, insert, commit, or
network work. The Recommendation READY gate is unchanged.

P4B.1 may observe eligible scoring items without changing their rank or relative scores. It uses the
source FeatureSnapshot `last_close` and official future sessions to store raw realized return, MFE,
and MAE only. Those outcomes are neither probabilities nor Recommendations; see
[forward outcomes](forward-outcomes.md).

P4B.2A joins these scores to versioned positive-close labels without changing P4A. Only
`SCORED_READY` items whose source quality is `READY` and whose score, rank, and FeatureSnapshot are
present enter `READY_SCORE_POSITIVE_CLOSE_CALIBRATION_DATASET/v1`. DEGRADED outcomes can still have
labels, but their different component availability keeps them out of the v1 calibration dataset.
The stored 0-to-100 score remains a relative score, never a probability.
