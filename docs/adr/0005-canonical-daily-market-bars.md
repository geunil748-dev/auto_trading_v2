# ADR 0005: Canonical completed daily market bars

## Status

Accepted for Prediction P2.

## Context

Prediction features must remain reproducible when the external market-data provider changes or
revises an earlier completed session. The existing `MarketSnapshot` is a point observation used by
candidate filtering and paper simulation; changing its meaning would couple prediction history to
that older execution flow.

## Decision

Add an independent immutable `DailyMarketBar` fact and `trading.daily_market_bars` table.
Provider semantic identity is `(source_code, source_record_key, source_version)`. Its canonical JSON
SHA-256 forms `daily-market-bar:v1:{digest}`. A separate content digest covers symbol, USD currency,
adjustment basis, session date, observed/available timestamps, OHLC, and nullable volume.

Revisions never overwrite a row. A provider supplies a new `source_version` or
`source_record_key`; feature reads select, for every session, the latest revision whose
`available_at <= as_of`. `0006_daily_market_bars` creates only this table and moves the canonical
table count from 13 to 14.

The v1 technical builder accepts exactly the latest 21 distinct `SPLIT_ADJUSTED` USD sessions from
one source and symbol. It calculates with a local Decimal precision of 38 and emits the existing
canonical `FeatureSnapshot` contract under `US_EQUITY_DAILY_TECHNICAL/v1`.

## Consequences

- `MarketSnapshot` remains unchanged.
- Daily bars have no FK to Candidate, StrategyDecision, TradeIntent, or Recommendation.
- Feature provenance stores only safe provider identity, timestamps, and each bar content digest.
- Actual provider HTTP adapters, exchange calendars, models, ranking, and Recommendation
  generation remain later work.
