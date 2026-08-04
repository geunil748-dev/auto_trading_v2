# ADR 0015: Verified multi-year US equity core-session calendar

- Status: Accepted
- Calendar code: `US_EQUITY_CORE`
- Calendar version: `2018-2026.v1`
- Coverage: 2018-01-01 through 2026-12-31
- Verified at: 2026-08-04

## Context

Historical DailyMarketBar research needs official session membership and close times before any
provider backfill can be reviewed. The existing immutable `2026.v1` calendar is correct for current
operational paths but intentionally cannot validate earlier dates. Guessing past closures from
recurring holiday rules would miss exceptional exchange decisions.

## Decision

Add a separate static calendar version whose repository-tracked data contains only derived closure
and early-close dates, safe reason codes, official source metadata, verification date, annual
counts, and deterministic digest. The source gate uses archived ICE/NYSE calendars, Nasdaq annual
calendars or official alert archives, and exchange notices for the 2018 and 2025 national days of
mourning. No raw official page or PDF is copied into the repository.

The adapter builds 2,262 immutable sessions for `XNGS`, `XNGM`, `XNCM`, `XNYS`, and `XASE` with
`ZoneInfo("America/New_York")`. Regular sessions are 09:30–16:00 ET; 20 documented early closes end
at 13:00 ET. There are 87 documented full closures, including the two exceptional mourning dates.
An inclusive pure `sessions_between` method supports future research and performs no I/O.

Selection requires the exact code and version. There is no latest-version lookup, date-based
selection, silent fallback, MIC inference from symbol, or calendar blending. Unsupported versions
and out-of-coverage dates fail closed.

## Compatibility and consequences

`US_EQUITY_CORE / 2026.v1` and all existing callers remain unchanged. For all 2026 dates and all
five MICs, the new calendar has exact session, family, kind, reason, local-time, and UTC-instant
parity; only the version differs. Existing completion grace and provider validation services work
through the injected calendar port.

This is a code/data boundary only. Alembic remains
`0010_outcome_labels_calibration_dataset`, canonical tables remain 25, and UoW repositories remain
19. Runtime network/provider calls, persistence writes, historical backfill, FeatureSnapshots,
scoring, models, Recommendation, TradeIntent, and orders are all zero. The next separately reviewed
slice is Historical DailyMarketBar Backfill Foundation.

## References

- [Tracked source metadata](../../src/auto_trading_v2/adapters/market_calendar/data/sources.py)
- [Tracked canonical schedule](../../src/auto_trading_v2/adapters/market_calendar/data/us_equity_core_2018_2026_v1.py)
- [NYSE Holidays and Trading Hours](https://www.nyse.com/markets/hours-calendars)
- [Nasdaq Trading Calendar](https://www.nasdaqtrader.com/Trader.aspx?id=Calendar)
- [Nasdaq 2018 Bush closure notice](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2018-98)
- [NYSE 2025 Carter closure notice](https://ir.theice.com/press/news-details/2024/The-New-York-Stock-Exchange-Will-Close-Markets-on-January-9-to-Honor-the-Passing-of-Former-President-Jimmy-Carter-on-National-Day-of-Mourning/default.aspx)
