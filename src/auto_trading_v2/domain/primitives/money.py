"""Currency and monetary amount value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from auto_trading_v2.domain.errors import CurrencyMismatchError, ValidationError

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Currency:
    """Three-letter currency code without an external ISO dependency."""

    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise ValidationError("통화 코드는 문자열이어야 합니다.")
        normalized = self.code.strip().upper()
        if not _CURRENCY_PATTERN.fullmatch(normalized):
            raise ValidationError("통화 코드는 영문 3자리여야 합니다.")
        object.__setattr__(self, "code", normalized)

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls(value)

    def serialize(self) -> str:
        return self.code

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True)
class Money:
    """Unquantized finite Decimal amount in a currency."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise ValidationError("금액은 Decimal이어야 하며 float를 암시적으로 변환하지 않습니다.")
        if not self.amount.is_finite():
            raise ValidationError("금액은 유한한 Decimal이어야 합니다.")
        if not isinstance(self.currency, Currency):
            raise ValidationError("금액에는 유효한 Currency가 필요합니다.")

    @classmethod
    def parse(cls, amount: str, currency: str) -> Self:
        try:
            parsed_amount = Decimal(amount)
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError("금액 문자열을 Decimal로 변환할 수 없습니다.") from exc
        return cls(parsed_amount, Currency.parse(currency))

    def serialize(self) -> dict[str, str]:
        return {"amount": str(self.amount), "currency": self.currency.serialize()}

    def _ensure_same_currency(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise TypeError("Money끼리만 연산할 수 있습니다.")
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"서로 다른 통화는 연산할 수 없습니다: {self.currency}, {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount - other.amount, self.currency)
