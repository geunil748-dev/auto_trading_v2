"""Thread-safe process-local Alpaca request rate limiter."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class AlpacaRequestRateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 200,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            isinstance(requests_per_minute, bool)
            or not isinstance(requests_per_minute, int)
            or requests_per_minute < 1
        ):
            raise ValueError("requests_per_minute must be a positive integer")
        self._requests_per_minute = requests_per_minute
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._window_started = monotonic()
        self._used = 0

    def acquire(self) -> None:
        while True:
            wait_seconds = 0.0
            with self._lock:
                now = self._monotonic()
                elapsed = now - self._window_started
                if elapsed >= 60.0 or elapsed < 0.0:
                    self._window_started = now
                    self._used = 0
                    elapsed = 0.0
                if self._used < self._requests_per_minute:
                    self._used += 1
                    return
                wait_seconds = max(0.0, 60.0 - elapsed)
            self._sleeper(wait_seconds)
