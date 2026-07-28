from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data.twelve_data import (
    TwelveDataCreditLimiter,
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def limiter(
    timer: FakeMonotonic,
    clock: FixedClock,
    *,
    minute: int = 8,
    daily: int = 800,
) -> TwelveDataCreditLimiter:
    return TwelveDataCreditLimiter(
        credits_per_minute=minute,
        daily_credit_budget=daily,
        clock=clock,
        monotonic=timer.now,
        sleeper=timer.sleep,
    )


def test_minute_limit_waits_with_injected_sleeper() -> None:
    timer = FakeMonotonic()
    subject = limiter(timer, FixedClock(datetime(2026, 7, 28, tzinfo=UTC)), minute=2)

    subject.acquire()
    subject.acquire()
    subject.acquire()

    assert timer.sleeps == [60.0]
    assert subject.daily_credits_used == 3


def test_minute_window_resets_without_sleep_after_elapsed_time() -> None:
    timer = FakeMonotonic()
    subject = limiter(timer, FixedClock(datetime(2026, 7, 28, tzinfo=UTC)), minute=1)
    subject.acquire()
    timer.value = 60.0

    subject.acquire()

    assert timer.sleeps == []


def test_daily_budget_blocks_before_another_request() -> None:
    timer = FakeMonotonic()
    subject = limiter(timer, FixedClock(datetime(2026, 7, 28, tzinfo=UTC)), daily=1)
    subject.acquire()

    with pytest.raises(TwelveDataProviderError) as raised:
        subject.acquire()

    assert raised.value.category is TwelveDataErrorCategory.DAILY_CREDIT_BUDGET_EXHAUSTED


def test_utc_day_change_resets_daily_budget() -> None:
    timer = FakeMonotonic()
    clock = FixedClock(datetime(2026, 7, 28, tzinfo=UTC))
    subject = limiter(timer, clock, daily=1)
    subject.acquire()
    clock.advance(timedelta(days=1))

    subject.acquire()

    assert subject.daily_credits_used == 1


def test_concurrent_acquire_is_atomic() -> None:
    timer = FakeMonotonic()
    subject = limiter(
        timer,
        FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
        minute=100,
        daily=100,
    )
    threads = [Thread(target=subject.acquire) for _ in range(20)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert subject.daily_credits_used == 20
