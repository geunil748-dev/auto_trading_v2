# ADR 0008: Versioned US equity core-session calendar

- Status: Accepted
- Calendar code: `US_EQUITY_CORE`
- Calendar version: `2026.v1`
- Verified at: `2026-07-31`

## Context

Daily-bar providers accepted a caller-supplied completed-session cutoff. Without a shared
exchange calendar, an operational caller could use a weekend, closure, incomplete regular
session, or incorrect fixed UTC offset. Reimplementing these rules per provider would also
allow Twelve Data and Alpaca to disagree before canonical persistence.

## Decision

The application uses a deterministic static adapter for the official 2026 NYSE and Nasdaq
US equity core-session schedule. It supports listing MICs `XNGS`, `XNGM`, `XNCM`, `XNYS`,
and `XASE`, preserving `NASDAQ_CORE` and `NYSE_CORE` families. `XNAS` is not treated as a
listing MIC or silently converted to `XNGS`.

Sessions use `ZoneInfo("America/New_York")`. Regular core hours are 09:30–16:00 ET and
the two explicit early closes end at 13:00 ET. Pre-market, after-hours, overnight, options
extensions, and NYSE Arca late sessions do not define canonical daily-bar completion.

The static source of truth contains ten explicit full-day closures and two explicit early
closes. It does not calculate holidays from recurring rules. The schedule has 251 trading
sessions, and 2026-07-03 is a full-day closure.

Scheduled close and daily-bar eligibility are separate. A caller supplies an immutable
`CompletionGracePeriod` from zero through 24 hours. A session becomes eligible at
`close_at + grace`, including exact equality. There is no hidden default.

`CompletedDailyBarsRequestFactory` resolves an operational cutoff without network access.
The existing explicit `completed_through_session_date` contract remains available for
backfill and replay. A shared validator rejects non-trading, future-cutoff, duplicate,
out-of-coverage, unsupported-MIC, and inconsistent provider sequences before persistence.
Calendar errors never trigger provider fallback.

## Coverage and versioning

Coverage is exactly 2026-01-01 through 2026-12-31. Inputs outside that exchange-calendar
range return `CALENDAR_OUT_OF_COVERAGE`; they never reuse the last 2026 session or infer a
future holiday. Supporting another year requires a new reviewed schedule version. Existing
`2026.v1` meaning must not change silently.

Unscheduled national-mourning closures, exchange emergencies, technical interruptions,
individual-symbol halts, and provider availability delays are not modeled. Emergency
overrides require a separate versioned design; provider publication delay remains a caller
grace policy.

## Consequences

- Twelve Data and Alpaca use one calendar validation boundary before persistence.
- DST changes alter UTC session times without fixed EST/EDT offsets.
- No schema, migration, scheduler, FeatureSnapshot, Recommendation, TradeIntent, or order
  behavior is added.
- External live tests calculate cutoffs through the resolver/factory but retain their
  credential gates.

## Official references

- [NYSE Holidays & Trading Hours](https://www.nyse.com/markets/hours-calendars)
- [Nasdaq U.S. Equity and Options Markets Holiday Schedule](https://www.nasdaqtrader.com/trader.aspx?id=calendar)
- [Python 3.12 `zoneinfo`](https://docs.python.org/3.12/library/zoneinfo.html)
