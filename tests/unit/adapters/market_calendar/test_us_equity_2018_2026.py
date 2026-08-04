from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from auto_trading_v2.adapters.market_calendar import (
    StaticOfficialUsEquityCalendar2018To2026,
)
from auto_trading_v2.adapters.market_calendar.data import ANNUAL_SCHEDULES
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarFamily,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
    MarketSessionKind,
    calendar_family_for_mic,
)
from auto_trading_v2.domain.primitives import SessionDate

_ET = ZoneInfo("America/New_York")
_DST_CASES = (
    (2018, "2018-03-09", "2018-03-12", "2018-11-02", "2018-11-05"),
    (2019, "2019-03-08", "2019-03-11", "2019-11-01", "2019-11-04"),
    (2020, "2020-03-06", "2020-03-09", "2020-10-30", "2020-11-02"),
    (2021, "2021-03-12", "2021-03-15", "2021-11-05", "2021-11-08"),
    (2022, "2022-03-11", "2022-03-14", "2022-11-04", "2022-11-07"),
    (2023, "2023-03-10", "2023-03-13", "2023-11-03", "2023-11-06"),
    (2024, "2024-03-08", "2024-03-11", "2024-11-01", "2024-11-04"),
    (2025, "2025-03-07", "2025-03-10", "2025-10-31", "2025-11-03"),
    (2026, "2026-03-06", "2026-03-09", "2026-10-30", "2026-11-02"),
)


@pytest.fixture
def calendar() -> StaticOfficialUsEquityCalendar2018To2026:
    return StaticOfficialUsEquityCalendar2018To2026()


def test_metadata_and_full_coverage(calendar: StaticOfficialUsEquityCalendar2018To2026) -> None:
    assert calendar.metadata.calendar_code is ExchangeCalendarCode.US_EQUITY_CORE
    assert calendar.metadata.calendar_version is ExchangeCalendarVersion.V2018_2026_1
    assert calendar.coverage.start == date(2018, 1, 1)
    assert calendar.coverage.end == date(2026, 12, 31)
    assert calendar.metadata.timezone_name == "America/New_York"
    assert len(calendar.sessions("XNGS")) == 2262


@pytest.mark.parametrize("schedule", ANNUAL_SCHEDULES)
def test_each_year_matches_manifest_and_session_hours(
    calendar: StaticOfficialUsEquityCalendar2018To2026,
    schedule,
) -> None:
    sessions = calendar.sessions_between(
        "XNGS", SessionDate(schedule.coverage_start), SessionDate(schedule.coverage_end)
    )
    assert len(sessions) == schedule.expected_session_count
    assert all(session.session_date.value.year == schedule.year for session in sessions)
    assert all(session.session_date.value.weekday() < 5 for session in sessions)
    assert all(
        session.open_at.astimezone(_ET).time().replace(tzinfo=None) == time(9, 30)
        for session in sessions
    )
    assert all(
        session.close_at.astimezone(_ET).time().replace(tzinfo=None)
        == (time(13) if session.session_kind is MarketSessionKind.EARLY_CLOSE else time(16))
        for session in sessions
    )


@pytest.mark.parametrize("schedule", ANNUAL_SCHEDULES)
def test_each_documented_closure_and_early_close_is_exact(
    calendar: StaticOfficialUsEquityCalendar2018To2026,
    schedule,
) -> None:
    for closed, _reason in schedule.closures:
        assert calendar.session_on("XNGS", SessionDate(closed)) is None
    for early, reason, close_time in schedule.early_closes:
        session = calendar.session_on("XNGS", SessionDate(early))
        assert session is not None
        assert session.session_kind is MarketSessionKind.EARLY_CLOSE
        assert session.reason_code == reason
        assert session.close_at.astimezone(_ET).time().replace(tzinfo=None) == close_time


@pytest.mark.parametrize("_year,spring_before,spring_after,fall_before,fall_after", _DST_CASES)
def test_zoneinfo_changes_utc_offsets_around_both_dst_transitions(
    calendar: StaticOfficialUsEquityCalendar2018To2026,
    _year: int,
    spring_before: str,
    spring_after: str,
    fall_before: str,
    fall_after: str,
) -> None:
    before_spring, after_spring, before_fall, after_fall = (
        calendar.session_on("XNYS", SessionDate.parse(value))
        for value in (spring_before, spring_after, fall_before, fall_after)
    )
    assert all(
        value is not None for value in (before_spring, after_spring, before_fall, after_fall)
    )
    assert before_spring is not None and before_spring.close_at.hour == 21
    assert after_spring is not None and after_spring.close_at.hour == 20
    assert before_fall is not None and before_fall.close_at.hour == 20
    assert after_fall is not None and after_fall.close_at.hour == 21
    assert all(
        value.open_at.astimezone(_ET).time().replace(tzinfo=None) == time(9, 30)
        and value.close_at.astimezone(_ET).time().replace(tzinfo=None) == time(16)
        for value in (before_spring, after_spring, before_fall, after_fall)
        if value is not None
    )


@pytest.mark.parametrize("mic", ("XNGS", "XNGM", "XNCM", "XNYS", "XASE"))
def test_supported_mics_are_exact_and_family_specific(
    calendar: StaticOfficialUsEquityCalendar2018To2026, mic: str
) -> None:
    session = calendar.session_on(mic, SessionDate.parse("2020-06-15"))
    assert session is not None
    assert session.mic_code == mic
    assert session.calendar_family is calendar_family_for_mic(mic)
    assert session.calendar_family in (
        ExchangeCalendarFamily.NASDAQ_CORE,
        ExchangeCalendarFamily.NYSE_CORE,
    )


@pytest.mark.parametrize("mic", ("XNAS", "ARCX", "", " ", None, 7))
def test_unsupported_or_malformed_mic_is_rejected(
    calendar: StaticOfficialUsEquityCalendar2018To2026, mic: object
) -> None:
    with pytest.raises(MarketCalendarValidationError):
        calendar.sessions(mic)  # type: ignore[arg-type]


def test_coverage_latest_and_range_boundaries_fail_closed(
    calendar: StaticOfficialUsEquityCalendar2018To2026,
) -> None:
    assert calendar.session_on("XNGS", SessionDate.parse("2017-12-31")) is None
    assert calendar.session_on("XNGS", SessionDate.parse("2027-01-01")) is None
    assert calendar.latest_session_on_or_before("XNGS", SessionDate.parse("2017-12-31")) is None
    assert calendar.latest_session_on_or_before("XNGS", SessionDate.parse("2027-01-01")) is None
    assert calendar.sessions("XNGS")[0].session_date == SessionDate.parse("2018-01-02")
    assert calendar.sessions("XNGS")[-1].session_date == SessionDate.parse("2026-12-31")
    assert calendar.latest_session_on_or_before(
        "XNGS", SessionDate.parse("2025-01-11")
    ).session_date == SessionDate.parse("2025-01-10")  # type: ignore[union-attr]
    assert calendar.latest_session_on_or_before(
        "XNGS", SessionDate.parse("2025-01-09")
    ).session_date == SessionDate.parse("2025-01-08")  # type: ignore[union-attr]


def test_range_is_inclusive_ordered_and_rejects_invalid_boundaries(
    calendar: StaticOfficialUsEquityCalendar2018To2026,
) -> None:
    values = calendar.sessions_between(
        "XNGS", SessionDate.parse("2019-12-30"), SessionDate.parse("2020-01-03")
    )
    assert [value.session_date.value for value in values] == [
        date(2019, 12, 30),
        date(2019, 12, 31),
        date(2020, 1, 2),
        date(2020, 1, 3),
    ]
    assert (
        len(
            calendar.sessions_between(
                "XNGS", SessionDate.parse("2018-01-01"), SessionDate.parse("2026-12-31")
            )
        )
        == 2262
    )
    assert (
        calendar.sessions_between(
            "XNGS", SessionDate.parse("2018-01-06"), SessionDate.parse("2018-01-07")
        )
        == ()
    )
    assert (
        len(
            calendar.sessions_between(
                "XNGS", SessionDate.parse("2024-07-03"), SessionDate.parse("2024-07-03")
            )
        )
        == 1
    )
    with pytest.raises(MarketCalendarValidationError, match="순서"):
        calendar.sessions_between(
            "XNGS", SessionDate.parse("2020-01-03"), SessionDate.parse("2020-01-02")
        )
    for start, end in (("2017-12-31", "2018-01-02"), ("2026-12-31", "2027-01-01")):
        with pytest.raises(MarketCalendarValidationError) as raised:
            calendar.sessions_between("XNGS", SessionDate.parse(start), SessionDate.parse(end))
        assert raised.value.category == "CALENDAR_OUT_OF_COVERAGE"


def test_utc_instants_are_timezone_aware(
    calendar: StaticOfficialUsEquityCalendar2018To2026,
) -> None:
    session = calendar.session_on("XNGS", SessionDate.parse("2024-07-03"))
    assert session is not None
    assert session.open_at.tzinfo is UTC
    assert session.close_at == datetime(2024, 7, 3, 17, tzinfo=UTC)
