"""Thread-safe process-local Twelve Data credit limiter."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import date

from auto_trading_v2.adapters.market_data.twelve_data.errors import (
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.ports.clock import Clock


class TwelveDataCreditLimiter:
    def __init__(
        self,
        *,
        credits_per_minute: int,
        daily_credit_budget: int,
        clock: Clock,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if credits_per_minute < 1 or daily_credit_budget < 1:
            raise ValueError("credit limits must be positive")
        self._credits_per_minute = credits_per_minute
        self._daily_credit_budget = daily_credit_budget
        self._clock = clock
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._minute_started = monotonic()
        self._minute_used = 0
        self._utc_day = self._current_day()
        self._daily_used = 0

    def acquire(self, credits: int = 1) -> None:
        if isinstance(credits, bool) or not isinstance(credits, int) or credits < 1:
            raise ValueError("credits must be a positive integer")
        if credits > self._credits_per_minute:
            raise TwelveDataProviderError(TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT)
        while True:
            wait_seconds = 0.0
            with self._lock:
                now = self._monotonic()
                self._refresh_locked(now)
                if self._daily_used + credits > self._daily_credit_budget:
                    raise TwelveDataProviderError(
                        TwelveDataErrorCategory.DAILY_CREDIT_BUDGET_EXHAUSTED
                    )
                elapsed = now - self._minute_started
                if self._minute_used + credits <= self._credits_per_minute:
                    self._minute_used += credits
                    self._daily_used += credits
                    return
                wait_seconds = max(0.0, 60.0 - elapsed)
            self._sleeper(wait_seconds)

    @property
    def daily_credits_used(self) -> int:
        with self._lock:
            self._refresh_locked(self._monotonic())
            return self._daily_used

    @property
    def available_daily_credits(self) -> int:
        with self._lock:
            self._refresh_locked(self._monotonic())
            return self._daily_credit_budget - self._daily_used

    @property
    def available_minute_credits(self) -> int:
        with self._lock:
            self._refresh_locked(self._monotonic())
            return self._credits_per_minute - self._minute_used

    def _refresh_locked(self, now: float) -> None:
        day = self._current_day()
        if day != self._utc_day:
            self._utc_day = day
            self._daily_used = 0
        elapsed = now - self._minute_started
        if elapsed >= 60 or elapsed < 0:
            self._minute_started = now
            self._minute_used = 0

    def _current_day(self) -> date:
        return normalize_utc(self._clock.now_utc()).date()
