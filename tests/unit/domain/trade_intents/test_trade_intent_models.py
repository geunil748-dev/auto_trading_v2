from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from auto_trading_v2.domain.primitives import Currency, Money, Quantity
from auto_trading_v2.domain.trade_intents import (
    FIXED_USD_NOTIONAL,
    FIXED_USD_NOTIONAL_VERSION,
    INITIAL_FIXED_USD_NOTIONAL_POLICY,
    EntrySizingResult,
    RiskOutcome,
    TimeInForce,
    TradeOrderType,
    TradeSide,
)
from auto_trading_v2.domain.trade_intents.errors import TradeIntentValidationError
from auto_trading_v2.domain.trade_intents.models import (
    FIXED_NOTIONAL_APPROVED,
    QUANTITY_BELOW_MINIMUM,
)


def test_enums_match_canonical_database_values() -> None:
    assert tuple(TradeSide) == (TradeSide.BUY, TradeSide.SELL)
    assert tuple(TradeOrderType) == (TradeOrderType.MARKET, TradeOrderType.LIMIT)
    assert tuple(TimeInForce) == (TimeInForce.DAY,)
    with pytest.raises(ValueError):
        TradeSide("HOLD")


def test_initial_policy_is_exact_immutable_and_code_defined() -> None:
    policy = INITIAL_FIXED_USD_NOTIONAL_POLICY

    assert policy.name == FIXED_USD_NOTIONAL
    assert policy.version == FIXED_USD_NOTIONAL_VERSION == "v1"
    assert policy.maximum_notional == Money(Decimal("1000"), Currency("USD"))
    assert policy.side is TradeSide.BUY
    assert policy.order_type is TradeOrderType.MARKET
    assert policy.time_in_force is TimeInForce.DAY
    assert policy.minimum_quantity == 1
    assert policy.fractional_quantity_allowed is False
    with pytest.raises(FrozenInstanceError):
        policy.version = "v2"  # type: ignore[misc]


def test_sizing_result_enforces_approved_and_rejected_shapes() -> None:
    approved = EntrySizingResult(
        FIXED_USD_NOTIONAL,
        "v1",
        RiskOutcome.APPROVED,
        Quantity(3),
        Money(Decimal("900"), Currency("USD")),
        (FIXED_NOTIONAL_APPROVED,),
    )
    rejected = EntrySizingResult(
        FIXED_USD_NOTIONAL,
        "v1",
        RiskOutcome.REJECTED,
        None,
        None,
        (QUANTITY_BELOW_MINIMUM,),
    )

    assert approved.requested_quantity == Quantity(3)
    assert rejected.requested_quantity is None
    with pytest.raises(TradeIntentValidationError):
        EntrySizingResult(
            FIXED_USD_NOTIONAL,
            "v1",
            RiskOutcome.APPROVED,
            None,
            None,
            (FIXED_NOTIONAL_APPROVED,),
        )
