from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.application.ports.batch_budget import DailyMarketDataProviderRole
from auto_trading_v2.application.ports.daily_market_data import (
    DailyMarketDataProviderCapabilities,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
)
from auto_trading_v2.domain.primitives import Currency


@dataclass
class ScriptedBatchBudget:
    consumed: int = 0

    @property
    def provider_code(self) -> str:
        return TWELVE_DATA_SOURCE_CODE

    @property
    def provider_role(self) -> DailyMarketDataProviderRole:
        return DailyMarketDataProviderRole.PRIMARY_FEATURE_SOURCE

    @property
    def enabled(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return True

    @property
    def maximum_rows_per_request(self) -> int:
        return 5000

    def estimate_maximum_cost(self, member_count: int, requested: int) -> int:
        return member_count

    def available_daily_budget(self) -> int:
        return 100 - self.consumed

    def available_minute_budget(self) -> int:
        return 8

    def consumed_daily_credits(self) -> int:
        return self.consumed


@dataclass
class ScriptedMultiSymbolProvider:
    budget: ScriptedBatchBudget
    calendar: StaticOfficialUsEquityCalendar2026
    calls: list[str] = field(default_factory=list)
    complete_price_mode: bool = False
    capabilities: DailyMarketDataProviderCapabilities = field(
        default_factory=lambda: DailyMarketDataProviderCapabilities(
            provider_code=TWELVE_DATA_SOURCE_CODE,
            official=True,
            requires_api_key=True,
            supports_raw_daily_bars=False,
            supports_split_adjusted_daily_bars=True,
            supports_adjusted_volume=False,
            supports_completed_cutoff=True,
            supports_pagination=False,
            maximum_rows_per_request=5000,
        )
    )

    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[DailyMarketBarInput, ...]:
        self.calls.append(request.symbol.value)
        self.budget.consumed += 1
        if request.symbol.value == "NVDA" and not self.complete_price_mode:
            raise TwelveDataProviderError(TwelveDataErrorCategory.INSTRUMENT_NOT_FOUND)
        assert request.source_code == TWELVE_DATA_SOURCE_CODE
        assert request.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
        assert request.mic_code == "XNGS"
        cutoff = request.completed_through_session_date
        assert cutoff is not None
        count = 21 if self.complete_price_mode or request.symbol.value == "AAPL" else 10
        sessions = tuple(
            session
            for session in self.calendar.sessions("XNGS")
            if session.session_date.value <= cutoff.value
        )[-count:]
        return tuple(self._bar(request, session, index) for index, session in enumerate(sessions))

    @staticmethod
    def _bar(
        request: FetchCompletedDailyBarsRequest, session: object, index: int
    ) -> DailyMarketBarInput:
        close = Decimal(100 + index)
        available_at = session.close_at
        return DailyMarketBarInput(
            source_code=TWELVE_DATA_SOURCE_CODE,
            source_record_key=(
                f"scripted-{request.symbol.value}-{session.session_date.serialize()}"
            ),
            source_version="scripted-v1",
            symbol=request.symbol,
            currency=Currency("USD"),
            adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            session_date=session.session_date,
            observed_at=available_at,
            available_at=available_at,
            open_price=close - Decimal("0.5"),
            high_price=close + Decimal(2),
            low_price=close - Decimal(2),
            close_price=close,
            volume=None,
        )
