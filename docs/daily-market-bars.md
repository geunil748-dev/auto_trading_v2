# Canonical DailyMarketBar

## Boundary

`MarketSnapshot` is an existing price observation for candidate/filter/paper simulation.
`DailyMarketBar` is a completed historical US-equity session used only as prediction feature input.
It is not attached directly to Candidate, StrategyDecision, TradeIntent, or Recommendation.

P2.1A extends the provider-neutral port with immutable capabilities and implements only the official
Twelve Data `/time_series` adapter. The caller selects `TWELVE_DATA_TIME_SERIES` explicitly.
KIS, Yahoo, Alpaca, Toss, Alpha Vantage, Finnhub, SEC, and FRED adapters remain outside this slice.
There is no silent fallback, cross-provider averaging, or mixed-source FeatureSnapshot.

## Time and revision policy

- `session_date`: US-market trading date represented by the completed bar.
- `observed_at`: source observation time of that completed bar.
- `available_at`: earliest time the provider made that version available.
- `recorded_at`: database insertion time, owned by MSSQL.

`observed_at <= available_at` is mandatory. A Point-in-Time query reads only
`available_at <= as_of`, selects the latest available revision for each session, limits by distinct
session, and returns chronological results. A revised provider record uses a new source record key
or version; rows are never updated, upserted, or replaced. Exchange-calendar freshness, holidays,
early closes, and DST session validation are not implemented.

Twelve Data does not expose the historical first-published time used by this contract. The first
successful UTC observation therefore becomes both `observed_at` and `available_at`; session close is
not guessed. Stable content re-fetches reuse the row and preserve that first `available_at`.
Corrected content gets a new immutable version whose `available_at` is its first observation.

## Identity and validation

Semantic identity is:

```text
source_code + source_record_key + source_version
```

Its sorted compact canonical JSON SHA-256 produces an 84-character key:

```text
daily-market-bar:v1:{64 lowercase hex}
```

The content digest includes symbol, USD, `RAW` or `SPLIT_ADJUSTED`, session date,
UTC-normalized observed/available timestamps, canonical Decimal OHLC, and nullable volume. ID,
bar key, and recorded time are excluded. Decimal representation and equivalent UTC offsets do not
change the digest.

Prices must be finite positive Decimal values; Python float is rejected. OHLC consistency and
non-negative integer-or-null volume are enforced in Domain and MSSQL. `RAW` is storable, but
technical feature set v1 accepts only `SPLIT_ADJUSTED`.

## Creation

`DailyMarketBarCreationService` performs one insert and one commit for new content. Exact retry
returns `ALREADY_EXISTS` with no ID, insert, or commit. Same identity with different content raises
a sanitized conflict. A unique race rolls back and rechecks through a fresh Unit of Work; no path
overwrites existing content.

## Twelve Data source identity

For `TWELVE_DATA_TIME_SERIES`, the record key contains MIC, symbol, session date, and adjustment
mode. The stable SHA-256 `source_version` covers adapter mapping version, provider symbol, MIC,
session, adjustment, mapped OHLC, and canonical nullable volume; it excludes fetch time, key, URL,
and raw payload.

`adjust=splits` is `SPLIT_ADJUSTED`, but adjusted volume compatibility is not verified, so canonical
volume is `None`. `adjust=none` is storable `RAW` and is rejected by the v1 technical builder.
