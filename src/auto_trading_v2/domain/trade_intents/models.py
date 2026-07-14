"""Immutable trade-intent enums and risk-sizing results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from auto_trading_v2.domain.primitives import Money, Quantity
from auto_trading_v2.domain.trade_intents.errors import TradeIntentValidationError

FIXED_NOTIONAL_APPROVED = "FIXED_NOTIONAL_APPROVED"
QUANTITY_BELOW_MINIMUM = "QUANTITY_BELOW_MINIMUM"


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TradeOrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TimeInForce(StrEnum):
    DAY = "DAY"


class RiskOutcome(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class EntrySizingResult:
    """Approved integer quantity or an explicit deterministic rejection."""

    policy_name: str
    policy_version: str
    outcome: RiskOutcome
    requested_quantity: Quantity | None
    estimated_notional: Money | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.policy_name, str) or not self.policy_name:
            raise TradeIntentValidationError("risk policy name is invalid")
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise TradeIntentValidationError("risk policy version is invalid")
        if not isinstance(self.outcome, RiskOutcome):
            raise TradeIntentValidationError("risk outcome is invalid")
        if not isinstance(self.reason_codes, tuple):
            raise TradeIntentValidationError("risk reason codes must be a tuple")
        if self.outcome is RiskOutcome.APPROVED:
            if (
                not isinstance(self.requested_quantity, Quantity)
                or self.requested_quantity.value < 1
                or not isinstance(self.estimated_notional, Money)
                or self.estimated_notional.amount < 0
                or self.reason_codes != (FIXED_NOTIONAL_APPROVED,)
            ):
                raise TradeIntentValidationError("approved sizing result is invalid")
        elif (
            self.requested_quantity is not None
            or self.estimated_notional is not None
            or self.reason_codes != (QUANTITY_BELOW_MINIMUM,)
        ):
            raise TradeIntentValidationError("rejected sizing result is invalid")
