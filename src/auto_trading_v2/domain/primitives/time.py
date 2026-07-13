"""UTC timestamp and session date value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from auto_trading_v2.domain.errors import InvalidTimestampError, ValidationError


def normalize_utc(value: datetime) -> datetime:
    """Validate an aware datetime and normalize it to UTC."""

    if not isinstance(value, datetime):
        raise InvalidTimestampError("타임스탬프는 datetime이어야 합니다.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidTimestampError("타임스탬프에는 시간대 정보가 필요합니다.")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class UtcTimestamp:
    """Immutable timezone-aware timestamp normalized to UTC."""

    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", normalize_utc(self.value))

    @classmethod
    def parse(cls, value: str) -> UtcTimestamp:
        if not isinstance(value, str):
            raise InvalidTimestampError("타임스탬프 문자열이 필요합니다.")
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            return cls(datetime.fromisoformat(normalized))
        except ValueError as exc:
            raise InvalidTimestampError("유효한 RFC 3339 타임스탬프가 아닙니다.") from exc

    def serialize(self) -> str:
        return self.value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SessionDate:
    """Calendar date only; exchange calendar rules are intentionally out of scope."""

    value: date

    def __post_init__(self) -> None:
        if type(self.value) is not date:
            raise ValidationError("세션 날짜는 datetime이 아닌 date여야 합니다.")

    @classmethod
    def parse(cls, value: str) -> SessionDate:
        try:
            return cls(date.fromisoformat(value))
        except (ValueError, TypeError) as exc:
            raise ValidationError("유효한 ISO 날짜가 아닙니다.") from exc

    def serialize(self) -> str:
        return self.value.isoformat()
