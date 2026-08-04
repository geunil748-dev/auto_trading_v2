"""Explicit static calendar version registry without latest-version fallback."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from auto_trading_v2.adapters.market_calendar.us_equity_2018_2026 import (
    StaticOfficialUsEquityCalendar2018To2026,
)
from auto_trading_v2.adapters.market_calendar.us_equity_2026 import (
    StaticOfficialUsEquityCalendar2026,
)
from auto_trading_v2.application.ports.market_calendar import UsEquityMarketCalendar
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
)

_CALENDARS: Mapping[
    tuple[ExchangeCalendarCode, ExchangeCalendarVersion], UsEquityMarketCalendar
] = MappingProxyType(
    {
        (ExchangeCalendarCode.US_EQUITY_CORE, ExchangeCalendarVersion.V2026_1): (
            StaticOfficialUsEquityCalendar2026()
        ),
        (ExchangeCalendarCode.US_EQUITY_CORE, ExchangeCalendarVersion.V2018_2026_1): (
            StaticOfficialUsEquityCalendar2018To2026()
        ),
    }
)


class StaticUsEquityCalendarRegistry:
    """Resolve only an exact supported calendar code/version pair."""

    @staticmethod
    def resolve(
        *,
        calendar_code: ExchangeCalendarCode,
        calendar_version: ExchangeCalendarVersion,
    ) -> UsEquityMarketCalendar:
        try:
            return _CALENDARS[(calendar_code, calendar_version)]
        except (KeyError, TypeError):
            raise MarketCalendarValidationError(
                "지원하지 않는 calendar code/version입니다.",
                category="CALENDAR_VERSION_UNSUPPORTED",
            ) from None
