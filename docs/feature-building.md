# Daily technical FeatureSnapshot building

## Fixed contract

- feature set: `US_EQUITY_DAILY_TECHNICAL`
- version: `v1`
- input: one source, one symbol, USD, `SPLIT_ADJUSTED`
- cutoff: every selected bar has `available_at <= as_of`
- window: latest 21 distinct completed sessions in chronological order
- horizon: caller-supplied existing `TradingDayHorizon` from 1 to 5
- arithmetic: local Decimal precision 38, `ROUND_HALF_EVEN`, no intermediate quantization

Let chronological bars be `b[0] … b[20]` and
`r[i] = close[i] / close[i-1] - 1` for `i=1 … 20`.

## Feature formulas and result types

All numeric results are Decimal values canonicalized by FeatureSnapshot to non-scientific JSON
strings. Unavailable volume features are JSON `null`. Metadata is a string and integer.

| Feature | Formula | Result |
| --- | --- | --- |
| `last_close` | `close[20]` | Decimal string |
| `one_day_return` | `close[20] / close[19] - 1` | Decimal string |
| `five_day_return` | `close[20] / close[15] - 1` | Decimal string |
| `twenty_day_return` | `close[20] / close[0] - 1` | Decimal string |
| `latest_gap_return` | `open[20] / close[19] - 1` | Decimal string |
| `latest_intraday_return` | `close[20] / open[20] - 1` | Decimal string |
| `latest_range_rate` | `(high[20] - low[20]) / close[19]` | Decimal string |
| `close_vs_sma5` | `close[20] / avg(close[16:21]) - 1` | Decimal string |
| `close_vs_sma10` | `close[20] / avg(close[11:21]) - 1` | Decimal string |
| `close_vs_sma20` | `close[20] / avg(close[1:21]) - 1` | Decimal string |
| `realized_volatility_20d` | population standard deviation of `r[1:21]`, denominator 20, no annualization | Decimal string |
| `atr14_rate` | `avg(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))) / close[20]`, `i=7…20` | Decimal string |
| `distance_from_prior_20d_high` | `close[20] / max(high[0:20]) - 1`; current high excluded | Decimal string |
| `distance_from_prior_20d_low` | `close[20] / min(low[0:20]) - 1`; current low excluded | Decimal string |
| `volume_ratio_5_to_20` | `avg(volume[16:21]) / avg(volume[1:21])` | Decimal string or null |
| `latest_volume_to_avg20` | `volume[20] / avg(volume[1:21])` | Decimal string or null |
| `average_dollar_volume_20` | `avg(close[i] * volume[i])`, `i=1…20` | Decimal string or null |

The payload also contains `adjustment_basis = "SPLIT_ADJUSTED"` and
`completed_bar_count = 21`.

## Quality outcomes

- `READY`: all 21 volumes exist and the 20-session average volume is positive.
- `DEGRADED / VOLUME_DATA_INCOMPLETE`: at least one volume is null.
- `DEGRADED / VOLUME_DATA_UNUSABLE`: all volumes exist but the 20-session average is zero.
- `DATA_INSUFFICIENT / INSUFFICIENT_COMPLETED_DAILY_BARS`: fewer than 21 price bars; no snapshot,
  ID, write, or commit occurs.

DEGRADED retains all price features and stores all three volume features as null.

## Explicit price-only v2 contract

`US_EQUITY_DAILY_TECHNICAL/v2` uses the same 21-bar PIT selection, provenance, local Decimal
context, metadata, and 14 price formulas listed above. It contains exactly those 14 numeric keys
plus `adjustment_basis = "SPLIT_ADJUSTED"` and `completed_bar_count = 21`. The keys
`volume_ratio_5_to_20`, `latest_volume_to_avg20`, and `average_dollar_volume_20` do not exist in the
v2 payload; absence is canonical and they are not stored as null.

Null, zero, and complete volume are ignored by v2, so complete prices yield `READY` with no quality
reason. Fewer than 21 bars still yield `DATA_INSUFFICIENT` without an ID, write, or commit. v1 is
unchanged and remains the default; callers use `BuildDailyPriceTechnicalFeatureSnapshotCommand`
and `DailyPriceTechnicalFeatureSnapshotService` to select v2 explicitly.

v2 `READY` is not a model, probability, profitable-trade claim, or Recommendation. Price-only and
volume-enhanced models may be compared only in later reviewed work.

## Orchestration and provenance

The pure builder has no Repository, Unit of Work, DB, Clock, UUID, config, network, Recommendation,
or TradeIntent dependency. The build service reads 21 PIT bars in one read-only Unit of Work, closes
that scope, calls the pure builder, and delegates valid input to the existing
`FeatureSnapshotCreationService`.

Provenance contains the 21 safe source identities, versions, observed/available timestamps, and
DailyMarketBar content digests. It does not duplicate raw prices or provider payloads. P2 does not
calculate a model, probability, rank, Recommendation, Outcome, or order.

## Twelve Data orchestration

`TwelveDataDailyFeatureService` is an explicit ingest-then-build boundary:

```text
TWELVE_DATA_TIME_SERIES ingest
→ immutable DailyMarketBar persistence
→ DailyTechnicalFeatureSnapshotService.build with the same source code
```

It never selects another provider and never passes `RAW` bars to the technical builder. With the
initial split-adjusted volume policy, 21 sessions produce
`DEGRADED / VOLUME_DATA_INCOMPLETE`: the 14 price features remain populated and
`volume_ratio_5_to_20`, `latest_volume_to_avg20`, and `average_dollar_volume_20` are null.
Allowed build outcomes remain `CREATED`, `ALREADY_EXISTS`, and `DATA_INSUFFICIENT`; no path creates
a Recommendation, TradeIntent, broker request, or order.

`TwelveDataDailyPriceFeatureService` is the separate explicit v2 boundary. It uses the same single
provider and immutable bars without fallback or synthesized volume; 21 complete-price/null-volume
bars produce a v2 `READY` snapshot.
