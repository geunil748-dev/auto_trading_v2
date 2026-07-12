"""Pure Decimal volatility-breakout calculations."""

from decimal import Decimal

from auto_trading_v2.domain.errors import InvalidBreakoutInputError
from auto_trading_v2.domain.primitives.numbers import Price


def _validate_inputs(previous_high: Price, previous_low: Price, factor: Decimal) -> None:
    if previous_high.value < previous_low.value:
        raise InvalidBreakoutInputError("전일 고가는 전일 저가보다 낮을 수 없습니다.")
    if not isinstance(factor, Decimal):
        raise InvalidBreakoutInputError("돌파 계수는 Decimal이어야 합니다.")
    if not factor.is_finite():
        raise InvalidBreakoutInputError("돌파 계수는 유한해야 합니다.")
    if factor < 0:
        raise InvalidBreakoutInputError("돌파 계수는 0 이상이어야 합니다.")


def volatility_breakout_price(
    current_open: Price,
    previous_high: Price,
    previous_low: Price,
    factor: Decimal,
) -> Price:
    """Return open + previous range * factor; zero factor is valid."""

    _validate_inputs(previous_high, previous_low, factor)
    target = current_open.value + (previous_high.value - previous_low.value) * factor
    return Price(target)


def breakout_triggered(
    current_price: Price,
    current_open: Price,
    previous_high: Price,
    previous_low: Price,
    factor: Decimal,
) -> bool:
    """Return whether the current price has reached the breakout target."""

    return (
        current_price.value
        >= volatility_breakout_price(current_open, previous_high, previous_low, factor).value
    )
