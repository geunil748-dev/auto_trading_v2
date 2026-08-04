# US equity core-session calendar

## Identity and support

| Field | Value |
| --- | --- |
| Calendar code | `US_EQUITY_CORE` |
| Version | `2026.v1` |
| Coverage | 2026-01-01 through 2026-12-31 |
| Time zone | `America/New_York` via `ZoneInfo` |
| Verified at | 2026-07-31 |
| Session count | 251 |

Supported listing MIC mapping:

- `XNGS`, `XNGM`, `XNCM` → `NASDAQ_CORE`
- `XNYS`, `XASE` → `NYSE_CORE`

`XNAS`, non-US MICs, blank values, and malformed MICs are rejected. The symbol is never
used to infer a MIC.

## Core-session contract

Regular sessions open at 09:30 ET and close at 16:00 ET. Early-close sessions open at
09:30 ET and close at 13:00 ET. Local exchange datetimes are constructed first and then
normalized to UTC, allowing IANA timezone data to apply DST. Pre-market, after-hours,
overnight, late trading, and options-only extensions are excluded.

DST examples locked by tests:

- 2026-03-06 close → 21:00 UTC; 2026-03-09 close → 20:00 UTC
- 2026-10-30 close → 20:00 UTC; 2026-11-02 close → 21:00 UTC

## Explicit 2026 schedule

Full-day closures:

- 2026-01-01 `NEW_YEARS_DAY`
- 2026-01-19 `MARTIN_LUTHER_KING_JR_DAY`
- 2026-02-16 `WASHINGTONS_BIRTHDAY`
- 2026-04-03 `GOOD_FRIDAY`
- 2026-05-25 `MEMORIAL_DAY`
- 2026-06-19 `JUNETEENTH`
- 2026-07-03 `INDEPENDENCE_DAY_OBSERVED`
- 2026-09-07 `LABOR_DAY`
- 2026-11-26 `THANKSGIVING_DAY`
- 2026-12-25 `CHRISTMAS_DAY`

Early closes at 13:00 ET (18:00 UTC):

- 2026-11-27 `DAY_AFTER_THANKSGIVING`
- 2026-12-24 `CHRISTMAS_EVE`

The adapter excludes weekends and the ten explicit closures from 261 weekdays. Early
closes remain trading sessions, producing 251 total sessions. It does not derive holidays
from annual rules.

## Completed-session and grace policy

Market close occurs at the scheduled `close_at`. Daily-bar eligibility occurs at
`close_at + completion_grace`. Grace is an explicit `timedelta` from zero through 24 hours;
there is no global default. Exact equality is eligible.

The resolver returns the latest eligible core session, the eligibility timestamp, normalized
UTC `as_of`, calendar identity, and previous session date. Weekends and closures resolve to
the prior eligible session. Before the first 2026 session completes it returns
`NO_COMPLETED_SESSION`. Outside 2026 it returns `CALENDAR_OUT_OF_COVERAGE`; 2027 never
returns 2026-12-31.

The request factory converts a resolved session into the existing explicit provider request.
Historical backfill/replay callers may still supply their own explicit cutoff. Failure results
contain no placeholder request, guessed session, network call, or persistence call.

## Provider response validation

After provider parsing and before any lookup or insert, the shared validator requires a
chronological single-symbol/single-source sequence of unique official trading sessions. It
rejects weekends, closures, dates after the completed cutoff, dates outside coverage,
unsupported MICs, duplicates, and inconsistent sequences. Errors expose only safe category
codes and never include raw payload or OHLC values. Validation failure causes zero
persistence and never selects another provider.

## Limits and annual updates

The schedule does not cover unscheduled mourning closures, exchange emergencies, technical
halts, individual-symbol halts, or provider outages. A future year or emergency override
requires a separately reviewed version. Provider publication delay is caller policy expressed
through completion grace. Scheduler and Recommendation/ranking remain unimplemented.

Official sources:

- [NYSE Holidays & Trading Hours](https://www.nyse.com/markets/hours-calendars)
- [Nasdaq trading calendar](https://www.nasdaqtrader.com/trader.aspx?id=calendar)
- [Python 3.12 `zoneinfo`](https://docs.python.org/3.12/library/zoneinfo.html)

## Explicit multi-year research version

The separate `US_EQUITY_CORE / 2018-2026.v1` adapter covers 2018-01-01 through
2026-12-31. Its serialized version retains the hyphen because the existing enum contract permits
that exact unambiguous value. Annual schedule counts are:

| Year | Sessions | Full closures | Early closes |
| --- | ---: | ---: | ---: |
| 2018 | 251 | 10 | 3 |
| 2019 | 252 | 9 | 3 |
| 2020 | 253 | 9 | 2 |
| 2021 | 252 | 9 | 1 |
| 2022 | 251 | 9 | 1 |
| 2023 | 250 | 10 | 2 |
| 2024 | 252 | 10 | 3 |
| 2025 | 250 | 11 | 3 |
| 2026 | 251 | 10 | 2 |

The tracked [canonical schedule data](../src/auto_trading_v2/adapters/market_calendar/data/us_equity_core_2018_2026_v1.py)
lists all 87 full closures and 20 early closes with safe reason codes. The only exceptional full
closures are 2018-12-05 for President George H. W. Bush and 2025-01-09 for President Jimmy Carter,
both supported by separate NYSE and Nasdaq notices. Manifest digest:
`1af97a32a7a0db2b441839c37017580937d42cdbeb92e032997b3087951f2ff3`.

`sessions_between` uses inclusive dates, returns chronological official sessions, permits an empty
valid range, and rejects reversed or partially out-of-coverage ranges. Completed-session resolution
still uses explicit caller grace; exact close plus grace is eligible, while dates after 2026-12-31
fail closed rather than returning the last session.

The static registry accepts only an exact code/version pair. It has no `latest`, wall-clock switch,
or fallback. Existing operational callers, P3 v1/v2, and `2026.v1` remain unchanged. Tests compare
every 2026 session across all five MICs; session date, MIC, family, kind, reason, and local/UTC times
are identical, with calendar version the sole difference.

Canonical dates come from archived official ICE/NYSE multi-year holiday announcements, official
NYSE holiday pages, Nasdaq annual trading calendars or archived Equity Trader alerts, and both
exchanges' official national-mourning notices. Recurring holiday rules and third-party libraries
are not the source of truth. Only derived dates, identifiers, URLs, verification metadata, counts,
and a deterministic digest are tracked; raw pages and PDFs are not stored. Runtime network calls
are zero.

This version includes the two officially verified mourning closures but does not model other
exchange emergencies, technical halts, individual-symbol halts, or provider outages. A future year
or new emergency requires a separately reviewed version. No migration, historical backfill,
FeatureSnapshot, scheduler, model, Recommendation, or order is added.

Additional official schedule evidence:

- [NYSE 2018–2020 calendar](https://ir.theice.com/press/news-details/2017/NYSE-Group-Announces-2018-2019-and-2020-Holiday-and-Early-Closings-Calendar/default.aspx)
- [NYSE 2021–2023 calendar](https://ir.theice.com/press/news-details/2020/NYSE-Group-Announces-2021-2022-and-2023-Holiday-and-Early-Closings-Calendar/default.aspx)
- [NYSE 2022–2024 calendar](https://ir.theice.com/press/news-details/2021/NYSE-Group-Announces-2022-2023-and-2024-Holiday-and-Early-Closings-Calendar/default.aspx)
- [NYSE 2023–2025 calendar](https://ir.theice.com/press/news-details/2022/NYSE-Group-Announces-2023-2024-and-2025-Holiday-and-Early-Closings-Calendar/default.aspx)
- [Nasdaq 2018 Bush closure notice](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2018-98)
- [NYSE 2025 Carter closure notice](https://ir.theice.com/press/news-details/2024/The-New-York-Stock-Exchange-Will-Close-Markets-on-January-9-to-Honor-the-Passing-of-Former-President-Jimmy-Carter-on-National-Day-of-Mourning/default.aspx)
