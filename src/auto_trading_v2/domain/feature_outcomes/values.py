"""Precision-38 Decimal value objects for raw forward outcomes."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext

from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)

OUTCOME_DECIMAL_CONTEXT = Context(prec=38, rounding=ROUND_HALF_EVEN)
_STORAGE_QUANTUM = Decimal("0.000000000000000001")


def canonical_outcome_decimal(value: object, category: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise OutcomeObservationValidationError(category)
    try:
        with localcontext(OUTCOME_DECIMAL_CONTEXT):
            return value.quantize(_STORAGE_QUANTUM)
    except InvalidOperation:
        raise OutcomeObservationValidationError(category) from None


def canonical_outcome_price(value: object, category: str) -> Decimal:
    normalized = canonical_outcome_decimal(value, category)
    if normalized <= 0:
        raise OutcomeObservationValidationError(category)
    return normalized


@dataclass(frozen=True, slots=True)
class ForwardReturn:
    value: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            canonical_outcome_decimal(self.value, "FORWARD_RETURN_INVALID"),
        )

    def serialize(self) -> str:
        return format(self.value, ".18f")


@dataclass(frozen=True, slots=True)
class ExcursionRate:
    value: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            canonical_outcome_decimal(self.value, "EXCURSION_RATE_INVALID"),
        )

    def serialize(self) -> str:
        return format(self.value, ".18f")
