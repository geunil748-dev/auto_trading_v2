"""Static official NYSE/Nasdaq US equity core sessions for 2018 through 2026."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from types import MappingProxyType
from zoneinfo import ZoneInfo

from auto_trading_v2.adapters.market_calendar.data import ANNUAL_SCHEDULES
from auto_trading_v2.domain.market_calendar import (
    CalendarCoverage,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarMetadata,
    MarketCalendarValidationError,
    MarketSession,
    MarketSessionKind,
    calendar_family_for_mic,
    normalize_supported_mic,
    supported_mic_codes,
)
from auto_trading_v2.domain.primitives import SessionDate

_NEW_YORK = ZoneInfo("America/New_York")
_COVERAGE = CalendarCoverage(date(2018, 1, 1), date(2026, 12, 31))
_CLOSURES = MappingProxyType(
    {day: reason for schedule in ANNUAL_SCHEDULES for day, reason in schedule.closures}
)
_EARLY_CLOSES = MappingProxyType(
    {
        day: (reason, close_time)
        for schedule in ANNUAL_SCHEDULES
        for day, reason, close_time in schedule.early_closes
    }
)
_METADATA = MarketCalendarMetadata(
    calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
    calendar_version=ExchangeCalendarVersion.V2018_2026_1,
    coverage=_COVERAGE,
    timezone_name="America/New_York",
    source_codes=tuple(source for year in ANNUAL_SCHEDULES for source in year.source_codes),
    verified_at=date(2026, 8, 4),
)


def _session_dates() -> tuple[date, ...]:
    current = _COVERAGE.start
    values: list[date] = []
    while current <= _COVERAGE.end:
        if current.weekday() < 5 and current not in _CLOSURES:
            values.append(current)
        current += timedelta(days=1)
    expected = sum(schedule.expected_session_count for schedule in ANNUAL_SCHEDULES)
    if len(values) != expected:
        raise RuntimeError("multi-year US equity session count does not match manifest")
    return tuple(values)


def _market_session(mic_code: str, session_date: date) -> MarketSession:
    early = _EARLY_CLOSES.get(session_date)
    kind = MarketSessionKind.EARLY_CLOSE if early is not None else MarketSessionKind.REGULAR
    close_time = early[1] if early is not None else time(16)
    return MarketSession(
        calendar_code=_METADATA.calendar_code,
        calendar_version=_METADATA.calendar_version,
        calendar_family=calendar_family_for_mic(mic_code),  # type: ignore[arg-type]
        mic_code=mic_code,
        session_date=SessionDate(session_date),
        open_at=datetime.combine(session_date, time(9, 30), _NEW_YORK),
        close_at=datetime.combine(session_date, close_time, _NEW_YORK),
        session_kind=kind,
        reason_code=None if early is None else early[0],
    )


_SESSIONS_BY_MIC = MappingProxyType(
    {
        mic: tuple(_market_session(mic, day) for day in _session_dates())
        for mic in supported_mic_codes()
    }
)
_SESSION_BY_MIC_AND_DATE = MappingProxyType(
    {
        (mic, session.session_date.value): session
        for mic, sessions in _SESSIONS_BY_MIC.items()
        for session in sessions
    }
)


def _range(start_date: SessionDate, end_date: SessionDate) -> tuple[date, date]:
    if not isinstance(start_date, SessionDate) or not isinstance(end_date, SessionDate):
        raise MarketCalendarValidationError(
            "calendar range 타입이 올바르지 않습니다.", category="CALENDAR_RANGE_INVALID"
        )
    start, end = start_date.value, end_date.value
    if start > end:
        raise MarketCalendarValidationError(
            "calendar range 순서가 올바르지 않습니다.", category="CALENDAR_RANGE_INVALID"
        )
    if not _COVERAGE.contains(start) or not _COVERAGE.contains(end):
        raise MarketCalendarValidationError(
            "calendar range가 coverage 밖입니다.", category="CALENDAR_OUT_OF_COVERAGE"
        )
    return start, end


class StaticOfficialUsEquityCalendar2018To2026:
    """Immutable precomputed 2018-2026 core-session schedule."""

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

    def sessions_between(
        self, mic_code: str, start_date: SessionDate, end_date: SessionDate
    ) -> tuple[MarketSession, ...]:
        start, end = _range(start_date, end_date)
        return tuple(
            session
            for session in self.sessions(mic_code)
            if start <= session.session_date.value <= end
        )

    def session_on(self, mic_code: str, session_date: SessionDate) -> MarketSession | None:
        normalized = normalize_supported_mic(mic_code)
        if not isinstance(session_date, SessionDate) or not _COVERAGE.contains(session_date.value):
            return None
        return _SESSION_BY_MIC_AND_DATE.get((normalized, session_date.value))

    def latest_session_on_or_before(
        self, mic_code: str, session_date: SessionDate
    ) -> MarketSession | None:
        if not isinstance(session_date, SessionDate) or not _COVERAGE.contains(session_date.value):
            return None
        for session in reversed(self.sessions(mic_code)):
            if session.session_date.value <= session_date.value:
                return session
        return None

    def is_trading_session(self, mic_code: str, session_date: SessionDate) -> bool:
        return self.session_on(mic_code, session_date) is not None
