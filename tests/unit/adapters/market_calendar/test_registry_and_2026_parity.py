from dataclasses import replace

import pytest

from auto_trading_v2.adapters.market_calendar import (
    StaticOfficialUsEquityCalendar2018To2026,
    StaticOfficialUsEquityCalendar2026,
    StaticUsEquityCalendarRegistry,
)
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
)


@pytest.mark.parametrize("mic", ("XNGS", "XNGM", "XNCM", "XNYS", "XASE"))
def test_all_2026_sessions_have_exact_semantic_parity_except_version(mic: str) -> None:
    existing = StaticOfficialUsEquityCalendar2026().sessions(mic)
    multi_year = tuple(
        session
        for session in StaticOfficialUsEquityCalendar2018To2026().sessions(mic)
        if session.session_date.value.year == 2026
    )

    assert len(existing) == len(multi_year) == 251
    assert [
        replace(value, calendar_version=ExchangeCalendarVersion.V2018_2026_1) for value in existing
    ] == list(multi_year)


def test_registry_requires_exact_code_and_version_without_fallback() -> None:
    existing = StaticUsEquityCalendarRegistry.resolve(
        calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
        calendar_version=ExchangeCalendarVersion.V2026_1,
    )
    historical = StaticUsEquityCalendarRegistry.resolve(
        calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
        calendar_version=ExchangeCalendarVersion.V2018_2026_1,
    )

    assert isinstance(existing, StaticOfficialUsEquityCalendar2026)
    assert isinstance(historical, StaticOfficialUsEquityCalendar2018To2026)
    with pytest.raises(MarketCalendarValidationError) as raised:
        StaticUsEquityCalendarRegistry.resolve(
            calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
            calendar_version="latest",  # type: ignore[arg-type]
        )
    assert raised.value.category == "CALENDAR_VERSION_UNSUPPORTED"
