"""Pure Decimal-only fixed-notional quantity planning."""

from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, localcontext

from auto_trading_v2.domain.primitives import Money, Price, Quantity
from auto_trading_v2.domain.trade_intents.models import (
    FIXED_NOTIONAL_APPROVED,
    QUANTITY_BELOW_MINIMUM,
    EntrySizingResult,
    RiskOutcome,
)
from auto_trading_v2.domain.trade_intents.risk import (
    INITIAL_FIXED_USD_NOTIONAL_POLICY,
    FixedNotionalRiskPolicy,
)


def plan_fixed_notional_quantity(
    reference_price: Price,
    policy: FixedNotionalRiskPolicy = INITIAL_FIXED_USD_NOTIONAL_POLICY,
) -> EntrySizingResult:
    """Floor maximum notional by reference price without changing global context."""

    with localcontext() as context:
        context.prec = 38
        context.rounding = ROUND_HALF_EVEN
        raw_quantity = policy.maximum_notional.amount / reference_price.value
        requested_value = int(raw_quantity.to_integral_value(rounding=ROUND_FLOOR))
        if requested_value < policy.minimum_quantity:
            return EntrySizingResult(
                policy.name,
                policy.version,
                RiskOutcome.REJECTED,
                None,
                None,
                (QUANTITY_BELOW_MINIMUM,),
            )
        quantity = Quantity(requested_value)
        estimated = Money(
            reference_price.value * Decimal(quantity.value),
            policy.maximum_notional.currency,
        )
    return EntrySizingResult(
        policy.name,
        policy.version,
        RiskOutcome.APPROVED,
        quantity,
        estimated,
        (FIXED_NOTIONAL_APPROVED,),
    )
