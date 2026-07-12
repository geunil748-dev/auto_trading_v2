"""Validated numeric value objects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from auto_trading_v2.domain.errors import ValidationError

DEFAULT_ROUNDING = ROUND_HALF_EVEN
"""Default rounding policy; PR 1 intentionally applies no universal quantization."""


def _validate_finite_decimal(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal):
        raise ValidationError(f"{label}은 Decimal이어야 하며 float를 암시적으로 변환하지 않습니다.")
    if not value.is_finite():
        raise ValidationError(f"{label}은 유한한 Decimal이어야 합니다.")


@dataclass(frozen=True, slots=True)
class Price:
    """Strictly positive price."""

    value: Decimal

    def __post_init__(self) -> None:
        _validate_finite_decimal(self.value, "가격")
        if self.value <= 0:
            raise ValidationError("가격은 0보다 커야 합니다.")

    @classmethod
    def parse(cls, value: str) -> Price:
        try:
            return cls(Decimal(value))
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError("가격 문자열을 Decimal로 변환할 수 없습니다.") from exc

    def serialize(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Quantity:
    """Non-negative integer quantity. Zero is valid."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValidationError("수량은 정수여야 합니다.")
        if self.value < 0:
            raise ValidationError("수량은 0 이상이어야 합니다.")

    def serialize(self) -> int:
        return self.value


@dataclass(frozen=True, slots=True)
class Rate:
    """Finite Decimal rate; negative values and values above one are valid."""

    value: Decimal

    def __post_init__(self) -> None:
        _validate_finite_decimal(self.value, "비율")

    @classmethod
    def parse(cls, value: str) -> Rate:
        try:
            return cls(Decimal(value))
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError("비율 문자열을 Decimal로 변환할 수 없습니다.") from exc

    def serialize(self) -> str:
        return str(self.value)
