from datetime import UTC, datetime

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data.twelve_data import (
    TwelveDataBatchBudgetAdapter,
    TwelveDataCreditLimiter,
)
from auto_trading_v2.application.ports.batch_budget import DailyMarketDataProviderRole
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.config.twelve_data import TwelveDataMarketDataSettings


def test_batch_budget_reuses_settings_capability_and_live_limiter_state() -> None:
    settings = TwelveDataMarketDataSettings(
        enabled=True,
        base_url="https://provider.invalid",
        api_key=SecretValue("configured-but-never-rendered"),
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        credits_per_minute=8,
        daily_credit_budget=10,
        maximum_retry_attempts=3,
        maximum_requests_per_operation=1,
    )
    limiter = TwelveDataCreditLimiter(
        credits_per_minute=8,
        daily_credit_budget=10,
        clock=FixedClock(datetime(2026, 8, 1, tzinfo=UTC)),
    )
    adapter = TwelveDataBatchBudgetAdapter(settings, limiter)

    assert adapter.provider_code == "TWELVE_DATA_TIME_SERIES"
    assert adapter.provider_role is DailyMarketDataProviderRole.PRIMARY_FEATURE_SOURCE
    assert adapter.enabled is True
    assert adapter.configured is True
    assert adapter.estimate_maximum_cost(3, 30) == 9
    assert adapter.available_daily_budget() == 10
    assert adapter.available_minute_budget() == 8
    limiter.acquire()
    assert adapter.available_daily_budget() == 9
    assert adapter.available_minute_budget() == 7
    assert adapter.consumed_daily_credits() == 1


def test_batch_budget_fails_closed_when_provider_capability_is_exceeded() -> None:
    settings = TwelveDataMarketDataSettings(
        True,
        "https://provider.invalid",
        SecretValue("configured-but-never-rendered"),
        1,
        1,
        8,
        10,
        3,
        1,
    )
    limiter = TwelveDataCreditLimiter(
        credits_per_minute=8,
        daily_credit_budget=10,
        clock=FixedClock(datetime(2026, 8, 1, tzinfo=UTC)),
    )
    adapter = TwelveDataBatchBudgetAdapter(settings, limiter)

    maximum = adapter.maximum_rows_per_request
    assert maximum is not None
    assert adapter.estimate_maximum_cost(1, maximum + 1) is None
