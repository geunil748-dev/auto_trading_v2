"""Deterministic exchange-calendar adapters."""

from auto_trading_v2.adapters.market_calendar.registry import (
    StaticUsEquityCalendarRegistry,
)
from auto_trading_v2.adapters.market_calendar.us_equity_2018_2026 import (
    StaticOfficialUsEquityCalendar2018To2026,
)
from auto_trading_v2.adapters.market_calendar.us_equity_2026 import (
    StaticOfficialUsEquityCalendar2026,
)

__all__ = [
    "StaticOfficialUsEquityCalendar2018To2026",
    "StaticOfficialUsEquityCalendar2026",
    "StaticUsEquityCalendarRegistry",
]
