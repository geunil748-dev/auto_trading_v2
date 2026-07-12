"""System and deterministic Clock implementations."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives.time import normalize_utc


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


@dataclass(slots=True)
class FixedClock:
    """Clock that changes only through explicit set or advance calls."""

    _current: datetime

    def __post_init__(self) -> None:
        self._current = normalize_utc(self._current)

    def now_utc(self) -> datetime:
        return self._current

    def set(self, value: datetime) -> None:
        self._current = normalize_utc(value)

    def advance(self, delta: timedelta) -> None:
        if not isinstance(delta, timedelta):
            raise ValidationError("시간 이동 값은 timedelta여야 합니다.")
        if delta < timedelta(0):
            raise ValidationError("FixedClock은 음수 시간만큼 되돌릴 수 없습니다.")
        self._current += delta
