# ADR 0007: Alpaca IEX validation provider and read-only comparison

## Status

Accepted for Prediction P2.1B. `verified_at=2026-07-29`.

## Context

Twelve Data is the implemented prediction-price source, but validation needs an independent
official observation without introducing fallback, provider blending, or a second trading path.
Alpaca's IEX feed represents one exchange rather than all US venues, so its role and metrics must
not imply whole-market equivalence.

## Decision

Add `ALPACA_IEX_STOCK_BARS` as an explicit validation-only `DailyMarketDataProvider`. It reads the
official single-stock historical bars endpoint with `feed=iex`, validates listing MIC identity
without sending MIC to the endpoint, authenticates only through protected headers, supports
split-adjusted and raw storage, preserves documented split-adjusted volume, and uses immutable
canonical revisions.

The adapter uses a process-local injected 200-request-per-minute limiter, bounded pagination, and
bounded retries only for timeout, connection failure, 429, 500, 502, 503, and 504. Sanitized
failures contain no URL, query, raw response, provider message, credential, header value, or page
token.

Add a read-only `DailyBarProviderComparisonService`. It queries each provider independently from
the existing repository, aligns by session, and computes close-relative-difference and return
direction metrics with local 38-digit `Decimal` precision and `ROUND_HALF_EVEN`. The report is
immutable and is not persisted.

## Consequences

- IEX is explicitly single-venue validation data, not a full-market substitute.
- Provider errors never trigger another provider.
- Comparison does not define tolerances, pass/fail thresholds, ranking, selection, or blending.
- Volume comparison and exact OHLC equality are excluded.
- No migration, canonical table, repository method, FeatureSnapshot, Recommendation, TradeIntent,
  broker, order, or execution behavior changes.
- Missing external credentials do not block local implementation or a Draft PR, but live status
  remains explicitly blocked rather than passed.
