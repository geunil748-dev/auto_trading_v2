"""Twelve Data adapter for provider-neutral P3 batch budget preflight."""

from dataclasses import dataclass, field

from auto_trading_v2.adapters.market_data.twelve_data.credit import TwelveDataCreditLimiter
from auto_trading_v2.adapters.market_data.twelve_data.parser import TWELVE_DATA_SOURCE_CODE
from auto_trading_v2.adapters.market_data.twelve_data.provider import TWELVE_DATA_CAPABILITIES
from auto_trading_v2.application.ports.batch_budget import DailyMarketDataProviderRole
from auto_trading_v2.config.twelve_data import TwelveDataMarketDataSettings


@dataclass(frozen=True, slots=True)
class TwelveDataBatchBudgetAdapter:
    settings: TwelveDataMarketDataSettings = field(repr=False)
    limiter: TwelveDataCreditLimiter = field(repr=False)

    @property
    def provider_code(self) -> str:
        return TWELVE_DATA_SOURCE_CODE

    @property
    def provider_role(self) -> DailyMarketDataProviderRole:
        return DailyMarketDataProviderRole.PRIMARY_FEATURE_SOURCE

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    @property
    def configured(self) -> bool:
        return self.settings.api_key is not None

    @property
    def maximum_rows_per_request(self) -> int | None:
        return TWELVE_DATA_CAPABILITIES.maximum_rows_per_request

    def estimate_maximum_cost(
        self,
        member_count: int,
        requested_session_count: int,
    ) -> int | None:
        maximum = self.maximum_rows_per_request
        if (
            isinstance(member_count, bool)
            or not isinstance(member_count, int)
            or member_count < 1
            or isinstance(requested_session_count, bool)
            or not isinstance(requested_session_count, int)
            or requested_session_count < 1
            or maximum is None
            or requested_session_count > maximum
        ):
            return None
        return member_count * self.settings.maximum_retry_attempts

    def available_daily_budget(self) -> int:
        return self.limiter.available_daily_credits

    def available_minute_budget(self) -> int:
        return self.limiter.available_minute_credits

    def consumed_daily_credits(self) -> int:
        return self.limiter.daily_credits_used
