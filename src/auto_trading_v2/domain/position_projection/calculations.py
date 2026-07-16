"""Decimal-only BUY quantity and weighted-average calculation."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from auto_trading_v2.domain.position_projection.errors import (
    PositionProjectionValidationError,
)
from auto_trading_v2.domain.primitives import Price, Quantity

_DECIMAL_SCALE = Decimal("0.000000000000000001")


@dataclass(frozen=True, slots=True)
class BuyPositionValues:
    """Position values after applying exactly one positive BUY Fill."""

    quantity: Quantity
    average_price: Price


def calculate_buy_position(
    *,
    fill_quantity: Quantity,
    fill_price: Price,
    current_quantity: Quantity | None = None,
    current_average_price: Price | None = None,
) -> BuyPositionValues:
    """Return scale-18 values using one final ROUND_HALF_EVEN quantization."""

    if not isinstance(fill_quantity, Quantity) or fill_quantity.value <= 0:
        raise PositionProjectionValidationError("fill quantity must be positive")
    if not isinstance(fill_price, Price):
        raise PositionProjectionValidationError("fill price is invalid")
    if (current_quantity is None) != (current_average_price is None):
        raise PositionProjectionValidationError("current position values are incomplete")
    if current_quantity is None:
        average = _quantize(fill_price.value)
        return BuyPositionValues(fill_quantity, Price(average))
    if current_quantity.value <= 0 or not isinstance(current_average_price, Price):
        raise PositionProjectionValidationError("current position is invalid")

    new_quantity = current_quantity.value + fill_quantity.value
    with localcontext() as context:
        context.prec = 80
        numerator = (
            Decimal(current_quantity.value) * current_average_price.value
            + Decimal(fill_quantity.value) * fill_price.value
        )
        average = _quantize(numerator / Decimal(new_quantity))
    return BuyPositionValues(Quantity(new_quantity), Price(average))


def _quantize(value: Decimal) -> Decimal:
    try:
        return value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_EVEN)
    except ArithmeticError as exc:
        raise PositionProjectionValidationError("average price cannot be represented") from exc
