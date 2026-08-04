from dataclasses import replace
from datetime import date

import pytest

from auto_trading_v2.adapters.market_calendar import (
    StaticOfficialUsEquityCalendar2018To2026,
)
from auto_trading_v2.application.services import DailyMarketBarCalendarValidator
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
)
from auto_trading_v2.domain.primitives import SessionDate
from tests.unit.domain.daily_market_bars.helpers import bar_input

pytestmark = pytest.mark.integration


def test_multi_year_range_returns_only_official_sessions_without_persistence() -> None:
    calendar = StaticOfficialUsEquityCalendar2018To2026()
    sessions = calendar.sessions_between(
        "XNGS", SessionDate.parse("2018-12-03"), SessionDate.parse("2025-01-10")
    )

    dates = {value.session_date.value for value in sessions}
    assert dates
    assert all(date(2018, 12, 3) <= value <= date(2025, 1, 10) for value in dates)
    assert all(value.weekday() < 5 for value in dates)
    assert date(2018, 12, 5) not in dates
    assert date(2025, 1, 9) not in dates
    assert date(2024, 7, 3) in dates


def test_scripted_historical_provider_validation_is_read_only_and_fail_closed() -> None:
    calendar = StaticOfficialUsEquityCalendar2018To2026()
    validator = DailyMarketBarCalendarValidator(calendar)

    def observation(value: str, index: int):
        return replace(
            bar_input(index),
            source_record_key=f"integration-history-{index}",
            session_date=SessionDate.parse(value),
        )

    valid = tuple(
        observation(value, index)
        for index, value in enumerate(("2018-12-04", "2018-12-06", "2024-07-03"))
    )
    result = validator.validate(
        mic_code="XNGS",
        calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
        calendar_version=ExchangeCalendarVersion.V2018_2026_1,
        completed_through_session_date=SessionDate.parse("2024-07-03"),
        observations=valid,
    )
    assert result == valid

    for invalid in ("2018-12-05", "2024-07-06", "2027-01-04"):
        with pytest.raises(MarketCalendarValidationError):
            validator.validate(
                mic_code="XNGS",
                calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
                calendar_version=ExchangeCalendarVersion.V2018_2026_1,
                completed_through_session_date=SessionDate.parse("2026-12-31"),
                observations=(observation(invalid, 10),),
            )
