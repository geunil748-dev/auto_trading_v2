# ADR 0006: Explicit multi-provider daily market data

## Status

Accepted for Prediction P2.1A. `verified_at=2026-07-28`.

## Context

Prediction input must continue to work when one market-data credential is unavailable, without
silently mixing providers or disguising an upstream failure as missing data. The canonical
`DailyMarketBar` identity and P2 Point-in-Time feature builder already preserve source provenance,
but P2 did not implement a network provider.

## Decision

Keep and extend the provider-neutral `DailyMarketDataProvider` port with immutable capability
metadata. A caller selects one explicit provider code. Every returned bar has that source code, and
one technical `FeatureSnapshot` reads bars from only one source. There is no automatic fallback,
cross-provider averaging, or provider-specific Recommendation/order path.

The first actual adapter is the official Twelve Data `/time_series` API under source code
`TWELVE_DATA_TIME_SERIES`. It supports XNAS, XNYS, and XASE, rejects other MICs before network I/O,
and requests `interval=1day` with an explicit `mic_code`. `adjust=splits` maps to
`SPLIT_ADJUSTED`; `adjust=none` maps to storable `RAW`.

Twelve Data does not provide a historical first-published timestamp in this response contract.
On first successful observation, `observed_at` and `available_at` both use that UTC observation
time. A stable content digest excludes fetch time. Exact content reuses the original row and its
first `available_at`; changed content creates a new immutable source version.

The official response includes volume, but its compatibility with split-adjusted prices has not
been verified. Split-adjusted canonical bars therefore store `volume=None`. The technical snapshot
is `DEGRADED / VOLUME_DATA_INCOMPLETE`, keeps 14 price features, and sets the three volume features
to null. `RAW` bars are never passed to the v1 technical builder.

## Consequences

- Provider failure remains an explicit sanitized outcome; it is never converted to `NO_DATA`.
- Provider selection changes provenance and creates provider-specific facts and snapshots.
- Free-plan credit numbers remain Twelve Data adapter settings, not Domain policy.
- No table or migration changes are required.
- Twelve Data configuration and transport stay outside Domain and do not create Recommendation,
  TradeIntent, broker, order, or execution side effects.
- Yahoo Finance remains unofficial/experimental. Alpaca, KIS, Toss Securities, Alpha Vantage,
  Finnhub, SEC EDGAR, and FRED remain documented future boundaries only.
