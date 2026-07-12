from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from auto_trading_v2.domain.errors import CurrencyMismatchError, ValidationError
from auto_trading_v2.domain.primitives.money import Currency, Money
from auto_trading_v2.domain.primitives.numbers import Price, Quantity, Rate
from auto_trading_v2.domain.primitives.symbol import Symbol


def test_symbol_normalizes_and_serializes() -> None:
    symbol = Symbol("  nvda ")

    assert symbol.value == "NVDA"
    assert symbol.serialize() == "NVDA"


@pytest.mark.parametrize("value", ["", "A/B", "A" * 33, "한글"])
def test_symbol_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValidationError):
        Symbol(value)


def test_currency_is_generic_and_normalized() -> None:
    assert Currency(" krw ").serialize() == "KRW"
    assert Currency("usd") != Currency("KRW")


@pytest.mark.parametrize("value", ["US", "USDT", "12A", "원화"])
def test_currency_rejects_invalid_codes(value: str) -> None:
    with pytest.raises(ValidationError):
        Currency(value)


def test_money_allows_zero_and_negative_and_serializes_decimal_as_string() -> None:
    zero = Money(Decimal("0"), Currency("KRW"))
    negative = Money(Decimal("-10.50"), Currency("KRW"))

    assert zero.amount == Decimal("0")
    assert negative.serialize() == {"amount": "-10.50", "currency": "KRW"}


def test_money_adds_and_subtracts_same_currency() -> None:
    left = Money(Decimal("10.25"), Currency("USD"))
    right = Money(Decimal("2.00"), Currency("USD"))

    assert (left + right).amount == Decimal("12.25")
    assert (left - right).amount == Decimal("8.25")


def test_money_rejects_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("1"), Currency("USD")) + Money(Decimal("1"), Currency("KRW"))


def test_money_rejects_float_and_non_finite_values() -> None:
    with pytest.raises(ValidationError):
        Money(1.2, Currency("USD"))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Money(Decimal("NaN"), Currency("USD"))


def test_price_is_positive_finite_decimal() -> None:
    assert Price(Decimal("1.25")).serialize() == "1.25"
    for value in (Decimal("0"), Decimal("-1"), Decimal("Infinity")):
        with pytest.raises(ValidationError):
            Price(value)
    with pytest.raises(ValidationError):
        Price(1.25)  # type: ignore[arg-type]


def test_quantity_allows_zero_and_rejects_negative_bool_and_fraction() -> None:
    assert Quantity(0).serialize() == 0
    for value in (-1, True, 1.5):
        with pytest.raises(ValidationError):
            Quantity(value)  # type: ignore[arg-type]


def test_rate_allows_negative_and_values_above_one_but_requires_finite_decimal() -> None:
    assert Rate(Decimal("-0.2")).value == Decimal("-0.2")
    assert Rate(Decimal("1.5")).serialize() == "1.5"
    for value in (Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValidationError):
            Rate(value)
    with pytest.raises(ValidationError):
        Rate(0.1)  # type: ignore[arg-type]


def test_value_objects_are_immutable() -> None:
    symbol = Symbol("MSFT")
    with pytest.raises(FrozenInstanceError):
        symbol.value = "AAPL"  # type: ignore[misc]
