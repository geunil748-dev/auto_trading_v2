# Canonical DailyMarketBar

## Boundary

`MarketSnapshot` is an existing price observation for candidate/filter/paper simulation.
`DailyMarketBar` is a completed historical US-equity session used only as prediction feature input.
It is not attached directly to Candidate, StrategyDecision, TradeIntent, or Recommendation.

P2 defines a provider-neutral port but performs no HTTP request and includes no KIS, Yahoo,
Polygon, Finnhub, token, parser, retry, or rate-limit adapter.

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
