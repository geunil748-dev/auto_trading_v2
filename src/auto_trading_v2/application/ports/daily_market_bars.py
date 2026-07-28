"""Insert-only canonical DailyMarketBar repository boundary."""

from datetime import datetime
from typing import Protocol

from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
)
from auto_trading_v2.domain.primitives import DailyMarketBarID, Symbol


class DailyMarketBarRepository(Protocol):
    def add(self, bar: NewDailyMarketBar) -> DailyMarketBar: ...

    def get_by_id(self, daily_market_bar_id: DailyMarketBarID) -> DailyMarketBar | None: ...

    def get_by_bar_key(self, bar_key: str) -> DailyMarketBar | None: ...

    def get_by_source_identity(
        self,
        source_code: str,
        source_record_key: str,
        source_version: str,
    ) -> DailyMarketBar | None: ...

    def list_latest_available(
        self,
        source_code: str,
        symbol: Symbol,
        adjustment_basis: DailyMarketBarAdjustmentBasis,
        as_of: datetime,
        limit: int,
    ) -> tuple[DailyMarketBar, ...]: ...
