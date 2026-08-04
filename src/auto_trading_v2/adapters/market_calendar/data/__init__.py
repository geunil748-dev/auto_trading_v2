"""Repository-tracked immutable market-calendar source data."""

from auto_trading_v2.adapters.market_calendar.data.sources import (
    OFFICIAL_SOURCES,
    OfficialScheduleSource,
)
from auto_trading_v2.adapters.market_calendar.data.us_equity_core_2018_2026_v1 import (
    ANNUAL_SCHEDULES,
    SOURCE_MANIFEST_DIGEST,
    AnnualOfficialSchedule,
)

__all__ = [
    "ANNUAL_SCHEDULES",
    "OFFICIAL_SOURCES",
    "SOURCE_MANIFEST_DIGEST",
    "AnnualOfficialSchedule",
    "OfficialScheduleSource",
]
