from decimal import Decimal

import pytest

from auto_trading_v2.domain.errors import InvalidBreakoutInputError
from auto_trading_v2.domain.primitives.numbers import Price
from auto_trading_v2.domain.strategy.breakout import (
    breakout_triggered,
    volatility_breakout_price,
)


def price(value: str) -> Price:
    return Price(Decimal(value))


def test_volatility_breakout_price_uses_decimal_formula() -> None:
    target = volatility_breakout_price(price("100"), price("120"), price("80"), Decimal("0.5"))

    assert target == price("120.0")


def test_volatility_breakout_price_preserves_decimal_precision() -> None:
    target = volatility_breakout_price(
        price("0.123456789123456789"),
        price("0.3"),
        price("0.1"),
        Decimal("0.123456789123456789"),
    )

    assert target.serialize() == "0.1481481469481481468"


def test_breakout_triggered_includes_exact_target() -> None:
    assert breakout_triggered(price("120"), price("100"), price("120"), price("80"), Decimal("0.5"))
    assert not breakout_triggered(
        price("119.99"), price("100"), price("120"), price("80"), Decimal("0.5")
    )


def test_zero_factor_is_allowed() -> None:
    assert volatility_breakout_price(
        price("100"), price("120"), price("80"), Decimal("0")
    ) == price("100")


def test_negative_factor_is_rejected() -> None:
    with pytest.raises(InvalidBreakoutInputError):
        volatility_breakout_price(price("100"), price("120"), price("80"), Decimal("-0.1"))


def test_previous_high_below_low_is_rejected() -> None:
    with pytest.raises(InvalidBreakoutInputError):
        volatility_breakout_price(price("100"), price("79"), price("80"), Decimal("0.5"))


def test_breakout_factor_rejects_float_and_non_finite_values() -> None:
    with pytest.raises(InvalidBreakoutInputError):
        volatility_breakout_price(price("100"), price("120"), price("80"), 0.5)  # type: ignore[arg-type]
    with pytest.raises(InvalidBreakoutInputError):
        volatility_breakout_price(price("100"), price("120"), price("80"), Decimal("NaN"))
