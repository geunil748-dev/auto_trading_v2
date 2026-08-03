"""Deterministic internal split-fill policy."""

from dataclasses import dataclass

from auto_trading_v2.domain.paper_fills.errors import PaperFillValidationError
from auto_trading_v2.domain.paper_fills.models import FillQuantityPlan
from auto_trading_v2.domain.primitives import Quantity

INTERNAL_PAPER_SPLIT_FILL_POLICY_NAME = "INTERNAL_PAPER_SPLIT_FILL"
INTERNAL_PAPER_SPLIT_FILL_POLICY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class InternalPaperSplitFillPolicy:
    """Split a positive integer quantity into at most two stable chunks."""

    def plan(self, requested_quantity: Quantity) -> FillQuantityPlan:
        if not isinstance(requested_quantity, Quantity) or requested_quantity.value <= 0:
            raise PaperFillValidationError("requested quantity must be positive")
        quantities: tuple[Quantity, ...]
        if requested_quantity.value == 1:
            quantities = (Quantity(1),)
        else:
            first = requested_quantity.value // 2
            quantities = (Quantity(first), Quantity(requested_quantity.value - first))
        return FillQuantityPlan(
            policy_name=INTERNAL_PAPER_SPLIT_FILL_POLICY_NAME,
            policy_version=INTERNAL_PAPER_SPLIT_FILL_POLICY_VERSION,
            requested_quantity=requested_quantity,
            quantities=quantities,
        )


INTERNAL_PAPER_SPLIT_FILL_POLICY = InternalPaperSplitFillPolicy()
