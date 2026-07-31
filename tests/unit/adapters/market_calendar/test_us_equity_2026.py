from datetime import UTC, date, datetime

import pytest

from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarFamily,
    ExchangeCalendarVersion,
    MarketSessionKind,
    calendar_family_for_mic,
)
from auto_trading_v2.domain.primitives import SessionDate


@pytest.fixture
def calendar() -> StaticOfficialUsEquityCalendar2026:
    return StaticOfficialUsEquityCalendar2026()


def test_metadata_and_official_schedule_counts(
    calendar: StaticOfficialUsEquityCalendar2026,
) -> None:
    metadata = calendar.metadata
    sessions = calendar.sessions("XNGS")

    assert metadata.calendar_code is ExchangeCalendarCode.US_EQUITY_CORE
    assert metadata.calendar_version is ExchangeCalendarVersion.V2026_1
    assert metadata.coverage.start == date(2026, 1, 1)
    assert metadata.coverage.end == date(2026, 12, 31)
    assert metadata.timezone_name == "America/New_York"
    assert metadata.source_codes == (
        "NYSE_OFFICIAL_2026_CALENDAR",
        "NASDAQ_OFFICIAL_2026_CALENDAR",
    )
    assert metadata.verified_at == date(2026, 7, 31)
    assert len(sessions) == 251
    assert sum(value.session_kind is MarketSessionKind.REGULAR for value in sessions) == 249
    assert sum(value.session_kind is MarketSessionKind.EARLY_CLOSE for value in sessions) == 2
    assert len(calendar.closure_dates) == 10


@pytest.mark.parametrize(
    "closed",
    (
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    ),
)
def test_explicit_closures_have_no_session(
    calendar: StaticOfficialUsEquityCalendar2026,
    closed: str,
) -> None:
    assert calendar.session_on("XNGS", SessionDate.parse(closed)) is None


@pytest.mark.parametrize("weekend", ("2026-07-04", "2026-07-05"))
def test_weekends_have_no_session(
    calendar: StaticOfficialUsEquityCalendar2026,
    weekend: str,
) -> None:
    assert calendar.session_on("XNYS", SessionDate.parse(weekend)) is None


@pytest.mark.parametrize("early", ("2026-11-27", "2026-12-24"))
def test_early_closes_are_trading_sessions_at_1800_utc(
    calendar: StaticOfficialUsEquityCalendar2026,
    early: str,
) -> None:
    session = calendar.session_on("XNGS", SessionDate.parse(early))

    assert session is not None
    assert session.session_kind is MarketSessionKind.EARLY_CLOSE
    assert session.close_at == datetime.fromisoformat(f"{early}T18:00:00+00:00")


@pytest.mark.parametrize(
    ("session_date", "utc_hour"),
    (("2026-03-06", 21), ("2026-03-09", 20), ("2026-10-30", 20), ("2026-11-02", 21)),
)
def test_zoneinfo_applies_dst_without_fixed_offsets(
    calendar: StaticOfficialUsEquityCalendar2026,
    session_date: str,
    utc_hour: int,
) -> None:
    session = calendar.session_on("XNGS", SessionDate.parse(session_date))

    assert session is not None
    assert session.close_at == datetime(
        2026,
        int(session_date[5:7]),
        int(session_date[8:]),
        utc_hour,
        tzinfo=UTC,
    )


@pytest.mark.parametrize("mic_code", ("XNGS", "XNGM", "XNCM", "XNYS", "XASE"))
def test_each_supported_mic_preserves_family_and_identity(
    calendar: StaticOfficialUsEquityCalendar2026,
    mic_code: str,
) -> None:
    session = calendar.session_on(mic_code, SessionDate.parse("2026-07-06"))

    assert session is not None
    assert session.mic_code == mic_code
    assert session.calendar_family is calendar_family_for_mic(mic_code)
    assert session.calendar_family in (
        ExchangeCalendarFamily.NASDAQ_CORE,
        ExchangeCalendarFamily.NYSE_CORE,
    )
