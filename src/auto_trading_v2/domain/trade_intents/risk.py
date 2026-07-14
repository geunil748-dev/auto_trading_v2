"""Versioned initial paper risk definition stored entirely in code."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from auto_trading_v2.domain.primitives import Currency, Money
from auto_trading_v2.domain.trade_intents.errors import TradeIntentValidationError
from auto_trading_v2.domain.trade_intents.models import (
    TimeInForce,
    TradeOrderType,
    TradeSide,
)

FIXED_USD_NOTIONAL = "FIXED_USD_NOTIONAL"
FIXED_USD_NOTIONAL_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class FixedNotionalRiskPolicy:
    """Immutable fixed-notional policy for an integer BUY market intent."""

    name: str
    version: str
    maximum_notional: Money
    side: TradeSide
    order_type: TradeOrderType
    time_in_force: TimeInForce
    minimum_quantity: int = 1
    fractional_quantity_allowed: bool = False

    def __post_init__(self) -> None:
        if self.name != FIXED_USD_NOTIONAL:
            raise TradeIntentValidationError("risk policy name is invalid")
        if (
            not isinstance(self.version, str)
            or not self.version
            or self.version != self.version.strip()
            or len(self.version) > 64
        ):
            raise TradeIntentValidationError("risk policy version is invalid")
        if (
            not isinstance(self.maximum_notional, Money)
            or self.maximum_notional.currency != Currency("USD")
            or self.maximum_notional.amount <= 0
        ):
            raise TradeIntentValidationError("risk policy notional is invalid")
        if self.side is not TradeSide.BUY or self.order_type is not TradeOrderType.MARKET:
            raise TradeIntentValidationError("risk policy order shape is invalid")
        if self.time_in_force is not TimeInForce.DAY:
            raise TradeIntentValidationError("risk policy time in force is invalid")
        if self.minimum_quantity != 1 or self.fractional_quantity_allowed:
            raise TradeIntentValidationError("risk policy quantity rule is invalid")


INITIAL_FIXED_USD_NOTIONAL_POLICY = FixedNotionalRiskPolicy(
    name=FIXED_USD_NOTIONAL,
    version=FIXED_USD_NOTIONAL_VERSION,
    maximum_notional=Money(Decimal("1000"), Currency("USD")),
    side=TradeSide.BUY,
    order_type=TradeOrderType.MARKET,
    time_in_force=TimeInForce.DAY,
)
