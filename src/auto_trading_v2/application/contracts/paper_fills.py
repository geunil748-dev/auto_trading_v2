"""Immutable application contracts for PaperFill creation and order transition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.paper_fills import validate_fill_transition
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import FillID, Money, OrderID, Price, Quantity
from auto_trading_v2.domain.primitives.time import normalize_utc


def _require_instance(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{label} has an invalid type")


@dataclass(frozen=True, slots=True)
class NewPaperFill:
    """Validated immutable fill accepted by a caller-owned transaction."""

    fill_id: FillID
    order_id: OrderID
    execution_key: str
    fill_sequence: int
    quantity: Quantity
    price: Price
    fee: Money
    executed_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.fill_id, FillID, "fill_id")
        _require_instance(self.order_id, OrderID, "order_id")
        _require_instance(self.quantity, Quantity, "quantity")
        _require_instance(self.price, Price, "price")
        _require_instance(self.fee, Money, "fee")
        if (
            not isinstance(self.execution_key, str)
            or not self.execution_key
            or self.execution_key != self.execution_key.strip()
            or len(self.execution_key) > 160
        ):
            raise ValidationError("execution_key is invalid")
        if (
            isinstance(self.fill_sequence, bool)
            or not isinstance(self.fill_sequence, int)
            or self.fill_sequence <= 0
        ):
            raise ValidationError("fill_sequence must be positive")
        if self.quantity.value <= 0:
            raise ValidationError("fill quantity must be positive")
        if self.fee.amount < 0:
            raise ValidationError("fill fee must be nonnegative")
        object.__setattr__(self, "executed_at", normalize_utc(self.executed_at))


@dataclass(frozen=True, slots=True)
class StoredPaperFill(NewPaperFill):
    """Canonical PaperFill including its database recording time."""

    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredPaperFill, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


@dataclass(frozen=True, slots=True)
class PaperOrderFillTransition:
    """The only PaperOrder mutation allowed after one canonical fill."""

    order_id: OrderID
    expected_status: PaperOrderStatus
    expected_version: int
    new_status: PaperOrderStatus
    closed_at: datetime | None
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.order_id, OrderID, "order_id")
        _require_instance(self.expected_status, PaperOrderStatus, "expected_status")
        _require_instance(self.new_status, PaperOrderStatus, "new_status")
        if (
            isinstance(self.expected_version, bool)
            or not isinstance(self.expected_version, int)
            or self.expected_version <= 0
        ):
            raise ValidationError("expected_version must be positive")
        updated_at = normalize_utc(self.updated_at)
        closed_at = None if self.closed_at is None else normalize_utc(self.closed_at)
        validate_fill_transition(
            expected_status=self.expected_status,
            new_status=self.new_status,
            closed_at=closed_at,
            updated_at=updated_at,
        )
        object.__setattr__(self, "closed_at", closed_at)
        object.__setattr__(self, "updated_at", updated_at)


@dataclass(frozen=True, slots=True)
class PaperFillExecutionResult:
    """The fill fact and transitioned current order returned together."""

    paper_fill: StoredPaperFill
    paper_order: StoredPaperOrder

    def __post_init__(self) -> None:
        _require_instance(self.paper_fill, StoredPaperFill, "paper_fill")
        _require_instance(self.paper_order, StoredPaperOrder, "paper_order")
