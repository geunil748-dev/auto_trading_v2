from decimal import ROUND_DOWN, Decimal, getcontext, localcontext

import pytest

from auto_trading_v2.domain.primitives import Money, Price, Quantity
from auto_trading_v2.domain.trade_intents import RiskOutcome, plan_fixed_notional_quantity


@pytest.mark.parametrize(
    ("price", "quantity", "estimated"),
    [
        ("25", 40, "1000"),
        ("300", 3, "900"),
        ("1000", 1, "1000"),
        ("333.333333333333333333", 3, "999.999999999999999999"),
    ],
)
def test_quantity_is_decimal_floor_with_canonical_types(
    price: str,
    quantity: int,
    estimated: str,
) -> None:
    result = plan_fixed_notional_quantity(Price(Decimal(price)))

    assert result.outcome is RiskOutcome.APPROVED
    assert result.requested_quantity == Quantity(quantity)
    assert result.estimated_notional == Money(
        Decimal(estimated),
        result.estimated_notional.currency,  # type: ignore[union-attr]
    )
    assert result.estimated_notional is not None
    assert result.estimated_notional.amount <= Decimal("1000")


def test_price_above_notional_is_explicitly_rejected() -> None:
    result = plan_fixed_notional_quantity(Price(Decimal("1000.000000000000000001")))

    assert result.outcome is RiskOutcome.REJECTED
    assert result.requested_quantity is None
    assert result.estimated_notional is None


def test_sizing_is_independent_of_and_does_not_mutate_decimal_context() -> None:
    original_precision = getcontext().prec
    original_rounding = getcontext().rounding
    price = Price(Decimal("37.123456789012345678"))

    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        low_context = plan_fixed_notional_quantity(price)
        assert context.prec == 6
        assert context.rounding == ROUND_DOWN
    high_context = plan_fixed_notional_quantity(price)

    assert low_context == high_context
    assert getcontext().prec == original_precision
    assert getcontext().rounding == original_rounding
