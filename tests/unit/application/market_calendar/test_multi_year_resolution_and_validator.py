from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from auto_trading_v2.adapters.market_calendar import (
    StaticOfficialUsEquityCalendar2018To2026,
)
from auto_trading_v2.application.services import (
    DailyMarketBarCalendarValidator,
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.domain.market_calendar import (
    CompletedSessionResolutionOutcome,
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
    ProviderBarCalendarErrorCategory,
)
from auto_trading_v2.domain.primitives import SessionDate
from tests.unit.domain.daily_market_bars.helpers import bar_input

_ET = ZoneInfo("America/New_York")
_CALENDAR = StaticOfficialUsEquityCalendar2018To2026()


def _resolve(value: str, grace_minutes: int = 0):
    return UsEquityCompletedSessionResolver(_CALENDAR).resolve(
        mic_code="XNGS",
        as_of=datetime.fromisoformat(value).replace(tzinfo=_ET),
        completion_grace=CompletionGracePeriod(timedelta(minutes=grace_minutes)),
    )


def _observation(value: str, index: int):
    return replace(
        bar_input(index),
        source_record_key=f"historical-{index}",
        session_date=SessionDate.parse(value),
    )


def _validate(*values: str, cutoff: str = "2025-01-10"):
    observations = tuple(_observation(value, index) for index, value in enumerate(values))
    return DailyMarketBarCalendarValidator(_CALENDAR).validate(
        mic_code="XNGS",
        calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
        calendar_version=ExchangeCalendarVersion.V2018_2026_1,
        completed_through_session_date=SessionDate.parse(cutoff),
        observations=observations,
    )


def test_completed_session_boundaries_and_explicit_grace() -> None:
    first_before = _resolve("2018-01-02T15:59:59")
    first_exact = _resolve("2018-01-02T16:00:00")
    grace_before = _resolve("2024-07-03T13:14:59", 15)
    grace_exact = _resolve("2024-07-03T13:15:00", 15)
    weekend = _resolve("2025-01-11T12:00:00")
    closure = _resolve("2025-01-09T12:00:00")

    assert first_before.outcome is CompletedSessionResolutionOutcome.NO_COMPLETED_SESSION
    assert first_exact.session is not None
    assert first_exact.session.session_date == SessionDate.parse("2018-01-02")
    assert grace_before.session is not None
    assert grace_before.session.session_date != SessionDate.parse("2024-07-03")
    assert grace_exact.session is not None
    assert grace_exact.session.session_date == SessionDate.parse("2024-07-03")
    assert weekend.session is not None and weekend.session.session_date == SessionDate.parse(
        "2025-01-10"
    )
    assert closure.session is not None and closure.session.session_date == SessionDate.parse(
        "2025-01-08"
    )


def test_completed_session_fails_closed_outside_multi_year_coverage() -> None:
    assert (
        _resolve("2017-12-31T12:00:00").outcome
        is CompletedSessionResolutionOutcome.CALENDAR_OUT_OF_COVERAGE
    )
    assert (
        _resolve("2027-01-01T12:00:00").outcome
        is CompletedSessionResolutionOutcome.CALENDAR_OUT_OF_COVERAGE
    )


def test_historical_provider_observations_validate_without_reordering() -> None:
    values = _validate("2019-12-31", "2020-01-02", "2024-07-03", "2025-01-10")
    assert [value.session_date.serialize() for value in values] == [
        "2019-12-31",
        "2020-01-02",
        "2024-07-03",
        "2025-01-10",
    ]


@pytest.mark.parametrize(
    ("value", "cutoff", "category"),
    (
        ("2025-01-11", "2025-01-11", ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY),
        ("2025-01-09", "2025-01-10", ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY),
        ("2027-01-04", "2026-12-31", ProviderBarCalendarErrorCategory.OUT_OF_CALENDAR_COVERAGE),
        ("2025-01-10", "2025-01-08", ProviderBarCalendarErrorCategory.AFTER_COMPLETED_CUTOFF),
    ),
)
def test_invalid_historical_observations_fail_with_safe_category(
    value: str, cutoff: str, category: ProviderBarCalendarErrorCategory
) -> None:
    with pytest.raises(MarketCalendarValidationError) as raised:
        _validate(value, cutoff=cutoff)
    assert raised.value.category == category.value
