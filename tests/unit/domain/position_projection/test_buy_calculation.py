from decimal import Decimal

import pytest

from auto_trading_v2.domain.position_projection import (
    PositionProjectionValidationError,
    calculate_buy_position,
)
from auto_trading_v2.domain.primitives import Price, Quantity


def test_first_buy_uses_fill_quantity_and_scale_18_price() -> None:
    result = calculate_buy_position(
        fill_quantity=Quantity(10),
        fill_price=Price(Decimal("100")),
    )

    assert result.quantity == Quantity(10)
    assert result.average_price == Price(Decimal("100.000000000000000000"))


def test_followup_buy_uses_exact_weighted_average() -> None:
    result = calculate_buy_position(
        current_quantity=Quantity(10),
        current_average_price=Price(Decimal("100")),
        fill_quantity=Quantity(5),
        fill_price=Price(Decimal("130")),
    )

    assert result.quantity == Quantity(15)
    assert result.average_price == Price(Decimal("110.000000000000000000"))


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (
            "1.000000000000000000",
            "1.000000000000000001",
            "1.000000000000000000",
        ),
        (
            "1.000000000000000001",
            "1.000000000000000002",
            "1.000000000000000002",
        ),
    ],
)
def test_round_half_even_is_applied_once_at_scale_boundary(
    first: str,
    second: str,
    expected: str,
) -> None:
    result = calculate_buy_position(
        current_quantity=Quantity(1),
        current_average_price=Price(Decimal(first)),
        fill_quantity=Quantity(1),
        fill_price=Price(Decimal(second)),
    )

    assert result.average_price == Price(Decimal(expected))


@pytest.mark.parametrize(
    "values",
    [
        {"fill_quantity": Quantity(0), "fill_price": Price(Decimal("1"))},
        {
            "fill_quantity": Quantity(1),
            "fill_price": Price(Decimal("1")),
            "current_quantity": Quantity(1),
        },
        {
            "fill_quantity": Quantity(1),
            "fill_price": Price(Decimal("1")),
            "current_quantity": Quantity(0),
            "current_average_price": Price(Decimal("1")),
        },
    ],
)
def test_invalid_projection_inputs_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(PositionProjectionValidationError):
        calculate_buy_position(**values)  # type: ignore[arg-type]
