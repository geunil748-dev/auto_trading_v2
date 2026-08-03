# Alpaca IEX daily-bar validation provider

## Role and coverage

`AlpacaDailyMarketDataProvider` is the validation-only implementation behind the provider-neutral
daily market-data port. Its source code is `ALPACA_IEX_STOCK_BARS`. It calls the official historical
single-symbol endpoint `GET /v2/stocks/{symbol}/bars` with `feed=iex`.

Alpaca describes IEX as one exchange and SIP as all US exchanges. Therefore this adapter does not
claim full-US-market coverage, does not replace Twelve Data, and is never an automatic fallback,
selection rule, or blended source.

Alpaca documents historical stock data availability from 2016 onward. This product limit is
documented as `verified_at=2026-07-29` and is not a Domain invariant because provider availability
and plans can change.

Official references:

- [Historical bars for one stock](https://docs.alpaca.markets/us/reference/stockbarsingle-1)
- [Market Data authentication](https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api)
- [Market Data FAQ: IEX versus SIP](https://docs.alpaca.markets/us/docs/market-data-faq)

## Exact request contract

The adapter accepts only listing MICs `XNGS`, `XNGM`, `XNCM`, `XNYS`, and `XASE`. AAPL is
`XNGS`. `XNAS` is not an alias and no MIC is inferred. MIC stays in canonical identity and is not
sent to Alpaca.

Static parameters are `timeframe=1Day`, `feed=iex`, `currency=USD`, `sort=asc`, and
`adjustment=split` or `raw`. The start is midnight UTC at least
`max(45, requested_session_count * 3)` calendar days before the completed cutoff. End is midnight
UTC on the next calendar day, `asof` is the cutoff date, and limit is positive, sufficient for the
requested count, and capped at 10,000.

Credentials are sent only in the `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` headers. They are
never query parameters and never appear in request/string representations, errors, diagnostics,
logs, cache, persistence, or raw output.

## Parsing, pagination, and revisions

JSON numbers are decoded with `parse_float=Decimal` and `parse_int=int`. The parser requires
RFC3339 UTC timestamps, maps them to the `America/New_York` session date with DST-aware rules,
filters after-cutoff rows, rejects duplicate sessions, validates positive Decimal OHLC and
non-negative integer volume, and validates optional trade-count/VWAP values without persisting
them. It sorts and returns only the latest requested distinct sessions.

Split adjustment preserves Alpaca's adjusted volume. RAW bars are storable but not automatically
used for feature construction.

Pagination stops on null or blank tokens, rejects malformed or repeated tokens, caps pages from
settings, and never renders a token. Each page and retry consumes the injected process-local rate
limiter. Only timeout, connection failure, HTTP 429, 500, 502, 503, and 504 are retried with bounded
attempts. All other HTTP failures are permanent and expose only category, operation, status,
numeric provider code, and a recognized parameter-name hint.

## Ingestion and comparison boundaries

`AlpacaDailyMarketBarIngestionService` creates or reuses immutable canonical bars and reports the
`iex` feed. It does not invoke FeatureSnapshot, Recommendation, TradeIntent, broker, or order code.

`DailyBarProviderComparisonService` reads primary and validation sources separately, aligns
sessions, and returns only an in-memory comparison report. It does not persist a new table, compare
volume, require exact OHLC equality, select a provider, or trigger trading behavior.

External tests are opt-in. Missing ignored-local or process credentials produce a real skip and
remain an explicit external-live blocker; a skip is never reported as a live pass.

## Exchange-calendar cutoff

Operational and credential-gated live requests use `US_EQUITY_CORE / 2026.v1` and an explicit
completion grace to select the latest eligible core session. Existing historical requests retain
their explicit cutoff. After IEX parsing, the common calendar validator rejects non-trading,
after-cutoff, duplicate, out-of-range, unsupported-MIC, or inconsistent rows before persistence.
Calendar failure never switches to Twelve Data or creates FeatureSnapshot, Recommendation,
TradeIntent, broker, or order side effects.
