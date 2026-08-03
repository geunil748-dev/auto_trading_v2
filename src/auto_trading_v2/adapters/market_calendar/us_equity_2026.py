"""Static official NYSE/Nasdaq US equity core-session schedule for 2026."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from types import MappingProxyType
from zoneinfo import ZoneInfo

from auto_trading_v2.domain.market_calendar import (
    CalendarCoverage,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarMetadata,
    MarketSession,
    MarketSessionKind,
    calendar_family_for_mic,
    normalize_supported_mic,
    supported_mic_codes,
)
from auto_trading_v2.domain.primitives import SessionDate

_NEW_YORK = ZoneInfo("America/New_York")
_COVERAGE = CalendarCoverage(date(2026, 1, 1), date(2026, 12, 31))
_CLOSURES = MappingProxyType(
    {
        date(2026, 1, 1): "NEW_YEARS_DAY",
        date(2026, 1, 19): "MARTIN_LUTHER_KING_JR_DAY",
        date(2026, 2, 16): "WASHINGTONS_BIRTHDAY",
        date(2026, 4, 3): "GOOD_FRIDAY",
        date(2026, 5, 25): "MEMORIAL_DAY",
        date(2026, 6, 19): "JUNETEENTH",
        date(2026, 7, 3): "INDEPENDENCE_DAY_OBSERVED",
        date(2026, 9, 7): "LABOR_DAY",
        date(2026, 11, 26): "THANKSGIVING_DAY",
        date(2026, 12, 25): "CHRISTMAS_DAY",
    }
)
_EARLY_CLOSES = MappingProxyType(
    {
        date(2026, 11, 27): "DAY_AFTER_THANKSGIVING",
        date(2026, 12, 24): "CHRISTMAS_EVE",
    }
)
_METADATA = MarketCalendarMetadata(
    calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
    calendar_version=ExchangeCalendarVersion.V2026_1,
    coverage=_COVERAGE,
    timezone_name="America/New_York",
    source_codes=(
        "NYSE_OFFICIAL_2026_CALENDAR",
        "NASDAQ_OFFICIAL_2026_CALENDAR",
    ),
    verified_at=date(2026, 7, 31),
)


def _session_dates() -> tuple[date, ...]:
    current = _COVERAGE.start
    values: list[date] = []
    while current <= _COVERAGE.end:
        if current.weekday() < 5 and current not in _CLOSURES:
            values.append(current)
        current += timedelta(days=1)
    if len(values) != 251:
        raise RuntimeError("US_EQUITY_CORE 2026 session count must be 251")
    return tuple(values)


def _market_session(mic_code: str, session_date: date) -> MarketSession:
    reason_code = _EARLY_CLOSES.get(session_date)
    kind = MarketSessionKind.EARLY_CLOSE if reason_code is not None else MarketSessionKind.REGULAR
    close_time = time(13) if kind is MarketSessionKind.EARLY_CLOSE else time(16)
    return MarketSession(
        calendar_code=_METADATA.calendar_code,
        calendar_version=_METADATA.calendar_version,
        calendar_family=calendar_family_for_mic(mic_code),  # type: ignore[arg-type]
        mic_code=mic_code,
        session_date=SessionDate(session_date),
        open_at=datetime.combine(session_date, time(9, 30), _NEW_YORK),
        close_at=datetime.combine(session_date, close_time, _NEW_YORK),
        session_kind=kind,
        reason_code=reason_code,
    )


_SESSIONS_BY_MIC = MappingProxyType(
    {
        mic_code: tuple(_market_session(mic_code, value) for value in _session_dates())
        for mic_code in supported_mic_codes()
    }
)
_SESSION_BY_MIC_AND_DATE = MappingProxyType(
    {
        (mic_code, session.session_date.value): session
        for mic_code, sessions in _SESSIONS_BY_MIC.items()
        for session in sessions
    }
)


class StaticOfficialUsEquityCalendar2026:
    """Immutable precomputed 2026 core-session schedule."""

    @property
    def metadata(self) -> MarketCalendarMetadata:
        return _METADATA

    @property
    def coverage(self) -> CalendarCoverage:
        return _COVERAGE

    @property
    def closure_dates(self) -> tuple[SessionDate, ...]:
        return tuple(SessionDate(value) for value in _CLOSURES)

    @property
    def early_close_dates(self) -> tuple[SessionDate, ...]:
        return tuple(SessionDate(value) for value in _EARLY_CLOSES)

    def sessions(self, mic_code: str) -> tuple[MarketSession, ...]:
        return _SESSIONS_BY_MIC[normalize_supported_mic(mic_code)]

    def session_on(
        self,
        mic_code: str,
        session_date: SessionDate,
    ) -> MarketSession | None:
        normalized = normalize_supported_mic(mic_code)
        if not isinstance(session_date, SessionDate):
            return None
        return _SESSION_BY_MIC_AND_DATE.get((normalized, session_date.value))

    def latest_session_on_or_before(
        self,
        mic_code: str,
        session_date: SessionDate,
    ) -> MarketSession | None:
        if not isinstance(session_date, SessionDate):
            return None
        for session in reversed(self.sessions(mic_code)):
            if session.session_date.value <= session_date.value:
                return session
        return None

    def is_trading_session(self, mic_code: str, session_date: SessionDate) -> bool:
        return self.session_on(mic_code, session_date) is not None
