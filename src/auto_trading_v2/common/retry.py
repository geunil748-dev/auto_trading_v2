"""Bounded retry helper with injected sleeping for deterministic tests."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from auto_trading_v2.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bound attempts and delays without providing semantic idempotency."""

    max_attempts: int
    retry_delay_seconds: float = 0.0
    request_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValidationError("최대 시도 횟수는 1 이상의 정수여야 합니다.")
        for delay in (self.retry_delay_seconds, self.request_delay_seconds):
            if isinstance(delay, bool) or not isinstance(delay, (int, float)):
                raise ValidationError("대기 시간은 숫자여야 합니다.")
            if not math.isfinite(delay) or delay < 0:
                raise ValidationError("대기 시간은 0 이상의 유한한 값이어야 합니다.")


def call_with_retry[ResultT](
    operation: Callable[[], ResultT],
    policy: RetryPolicy,
    *,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    sleeper: Callable[[float], None] = time.sleep,
) -> ResultT:
    """Retry failures up to max_attempts and re-raise the original final exception.

    This helper does not provide business idempotency or duplicate-order protection.
    """

    if not retryable_exceptions:
        raise ValidationError("재시도 가능한 예외 타입을 하나 이상 지정해야 합니다.")
    sleeper(float(policy.request_delay_seconds))
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if not isinstance(exc, retryable_exceptions) or attempt == policy.max_attempts:
                raise
            sleeper(float(policy.retry_delay_seconds))
    raise AssertionError("retry loop exited unexpectedly")
