# Twelve Data daily market-data provider

## Scope

`TwelveDataDailyMarketDataProvider` is the first actual provider behind the provider-neutral daily
market-data port. Its source code is `TWELVE_DATA_TIME_SERIES`; it uses only the official
`GET /time_series` endpoint and never falls back to another provider.

The implemented request contract is:

- `symbol=<caller symbol>`
- `mic_code=XNGS|XNGM|XNCM|XNYS|XASE` (listing MIC; no operating-MIC aliasing)
- `interval=1day`
- `outputsize=<requested completed sessions>`, bounded by the official 5,000-row maximum
- `end_date=<explicit completed cutoff YYYY-MM-DD>`
- `adjust=splits` for `SPLIT_ADJUSTED`, or `adjust=none` for `RAW`
- `order=asc`
- `Authorization: apikey <secret>` header; no API key is placed in the query string

The adapter validates the endpoint response's symbol, USD currency, MIC/exchange, exchange
timezone, and daily interval. It parses finite Decimal strings directly, rejects blank/invalid
OHLC, invalid dates, negative volume, duplicate sessions, and permanent provider errors, filters
rows after the completed cutoff, trims to the newest requested sessions, and returns chronological
bars. Raw URLs, query strings, API keys, response bodies, and provider payloads are not logged or
persisted.

The official contract and limits were verified on 2026-07-28 against the
[Twelve Data API documentation](https://twelvedata.com/docs),
[pricing page](https://twelvedata.com/pricing), and
[credit guidance](https://support.twelvedata.com/en/articles/5615854-credits).
The endpoint costs one credit per symbol. `outputsize` and explicit date range provide the
documented historical-window semantics; the P2.1A adapter deliberately performs one request per
operation by default instead of hidden pagination.

## Adjustment and quality

`adjust=splits` maps to `DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED`. Twelve Data returns volume,
but official evidence that it is adjusted on exactly the same split basis was not established.
Accordingly, canonical split-adjusted volume is always `None`. A 21-session technical build is
`DEGRADED / VOLUME_DATA_INCOMPLETE`: all 14 price features are present and all three volume
features are null.

`adjust=none` maps to `RAW`. RAW bars can be ingested and retained as independent facts but cannot
enter `US_EQUITY_DAILY_TECHNICAL/v1`.

## Credit and retry

The process-local, thread-safe limiter defaults to 8 credits per rolling minute and 800 credits per
UTC day. It reserves credit before network I/O, waits with injected clocks/sleeper for a minute
window, resets at a UTC-day boundary, and blocks before network I/O when the daily budget is
exhausted.

Retries are bounded deterministic exponential backoff for timeouts, HTTP 429, HTTP 5xx, and
explicitly temporary provider errors. HTTP 400, 401, 403, and 404 are distinct non-retryable
categories. Raw error messages and bodies are discarded; diagnostics retain only the HTTP status,
numeric provider code, and a recognized parameter-name hint.

## Point-in-Time revisions

The first successful fetch observation supplies both `observed_at` and `available_at`; no historical
session-close time is invented. `source_record_key` identifies MIC, symbol, session, and adjustment.
`source_version` is a SHA-256 digest of mapping version, symbol, MIC, session, adjustment, mapped
OHLC, and canonical nullable volume. Fetch time, key, URL, and raw payload are excluded.

Exact content reuses the existing immutable bar and preserves its original `available_at`. Corrected
provider content receives a new version and the first observation time of that revision.

## Live gate

The local scripted transport, unit suite, and temporary MSSQL SQLAlchemy/.NET contract do not need
an external key. The credential-gated live test uses the AAPL listing MIC `XNGS` only when an
ignored local `.env` or process environment enables Twelve Data and supplies a key. The external
request sends the credential only in the Authorization header.
