"""Immutable domain results for deterministic paper-fill planning."""

from dataclasses import dataclass

from auto_trading_v2.domain.paper_fills.errors import PaperFillValidationError
from auto_trading_v2.domain.primitives import Quantity


@dataclass(frozen=True, slots=True)
class FillQuantityPlan:
    """A versioned, positive integer fill plan."""

    policy_name: str
    policy_version: str
    requested_quantity: Quantity
    quantities: tuple[Quantity, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.policy_name, str) or not self.policy_name:
            raise PaperFillValidationError("fill policy name is invalid")
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise PaperFillValidationError("fill policy version is invalid")
        if not isinstance(self.requested_quantity, Quantity):
            raise PaperFillValidationError("requested quantity is invalid")
        if not isinstance(self.quantities, tuple) or not 1 <= len(self.quantities) <= 2:
            raise PaperFillValidationError("fill quantities are invalid")
        if any(not isinstance(item, Quantity) or item.value <= 0 for item in self.quantities):
            raise PaperFillValidationError("fill quantity must be positive")
        if sum(item.value for item in self.quantities) != self.requested_quantity.value:
            raise PaperFillValidationError("fill quantities do not match requested quantity")
