"""Trading symbol value object."""

import re
from dataclasses import dataclass
from typing import Self

from auto_trading_v2.domain.errors import ValidationError

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,31}$")


@dataclass(frozen=True, slots=True)
class Symbol:
    """Normalized symbol containing letters, digits, dot, or hyphen."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValidationError("종목코드는 문자열이어야 합니다.")
        normalized = self.value.strip().upper()
        if not _SYMBOL_PATTERN.fullmatch(normalized):
            raise ValidationError(
                "종목코드는 1~32자의 영문 대문자, 숫자, 점 또는 하이픈이어야 합니다."
            )
        object.__setattr__(self, "value", normalized)

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls(value)

    def serialize(self) -> str:
        return self.value

    def __str__(self) -> str:
        return self.value
