"""Immutable application contracts for paper-order submission and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.paper_orders import (
    PaperBrokerSubmissionOutcome,
    PaperOrderStatus,
    validate_paper_order_state,
)
from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    Currency,
    OrderID,
    Price,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide


def _require_instance(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{label} has an invalid type")


def _validate_code(value: str | None, label: str, maximum: int, *, optional: bool) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValidationError(f"{label} is invalid")


def _normalize_optional(value: datetime | None) -> datetime | None:
    return None if value is None else normalize_utc(value)


@dataclass(frozen=True, slots=True)
class PaperOrderSubmissionRequest:
    """Validated values sent to a paper broker."""

    trade_intent_id: TradeIntentID
    client_order_id: ClientOrderID
    symbol: Symbol
    currency: Currency
    side: TradeSide
    order_type: TradeOrderType
    requested_quantity: Quantity
    limit_price: Price | None
    time_in_force: TimeInForce
    submitted_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.trade_intent_id, TradeIntentID, "trade_intent_id")
        _require_instance(self.client_order_id, ClientOrderID, "client_order_id")
        _require_instance(self.symbol, Symbol, "symbol")
        _require_instance(self.currency, Currency, "currency")
        _require_instance(self.side, TradeSide, "side")
        _require_instance(self.order_type, TradeOrderType, "order_type")
        _require_instance(self.requested_quantity, Quantity, "requested_quantity")
        _require_instance(self.time_in_force, TimeInForce, "time_in_force")
        if self.requested_quantity.value <= 0:
            raise ValidationError("requested_quantity must be positive")
        if self.order_type is TradeOrderType.MARKET and self.limit_price is not None:
            raise ValidationError("MARKET request must not have a limit price")
        if self.order_type is TradeOrderType.LIMIT and not isinstance(self.limit_price, Price):
            raise ValidationError("LIMIT request requires a valid limit price")
        object.__setattr__(self, "submitted_at", normalize_utc(self.submitted_at))


@dataclass(frozen=True, slots=True)
class PaperOrderSubmissionResult:
    """Validated response returned by a paper broker."""

    outcome: PaperBrokerSubmissionOutcome
    broker_code: str
    broker_order_ref: str | None
    processed_at: datetime
    rejection_code: str | None

    def __post_init__(self) -> None:
        _require_instance(self.outcome, PaperBrokerSubmissionOutcome, "outcome")
        _validate_code(self.broker_code, "broker_code", 32, optional=False)
        _validate_code(self.broker_order_ref, "broker_order_ref", 160, optional=True)
        _validate_code(self.rejection_code, "rejection_code", 64, optional=True)
        if self.outcome is PaperBrokerSubmissionOutcome.ACCEPTED:
            if self.broker_order_ref is None or self.rejection_code is not None:
                raise ValidationError("accepted broker result is invalid")
        elif self.rejection_code is None:
            raise ValidationError("rejected broker result requires a rejection code")
        object.__setattr__(self, "processed_at", normalize_utc(self.processed_at))


@dataclass(frozen=True, slots=True)
class NewPaperOrder:
    """Validated paper-order values accepted by a caller-owned transaction."""

    order_id: OrderID
    trade_intent_id: TradeIntentID
    client_order_id: ClientOrderID
    broker_code: str
    broker_order_ref: str | None
    status: PaperOrderStatus
    rejection_code: str | None
    submitted_at: datetime
    accepted_at: datetime | None
    closed_at: datetime | None
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.order_id, OrderID, "order_id")
        _require_instance(self.trade_intent_id, TradeIntentID, "trade_intent_id")
        _require_instance(self.client_order_id, ClientOrderID, "client_order_id")
        _require_instance(self.status, PaperOrderStatus, "status")
        _validate_code(self.broker_code, "broker_code", 32, optional=False)
        _validate_code(self.broker_order_ref, "broker_order_ref", 160, optional=True)
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise ValidationError("version must be positive")
        submitted_at = normalize_utc(self.submitted_at)
        accepted_at = _normalize_optional(self.accepted_at)
        closed_at = _normalize_optional(self.closed_at)
        updated_at = normalize_utc(self.updated_at)
        if updated_at < submitted_at:
            raise ValidationError("updated_at precedes submitted_at")
        if accepted_at is not None and accepted_at < submitted_at:
            raise ValidationError("accepted_at precedes submitted_at")
        if closed_at is not None and closed_at < submitted_at:
            raise ValidationError("closed_at precedes submitted_at")
        validate_paper_order_state(
            status=self.status,
            accepted_at=accepted_at,
            closed_at=closed_at,
            rejection_code=self.rejection_code,
        )
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(self, "accepted_at", accepted_at)
        object.__setattr__(self, "closed_at", closed_at)
        object.__setattr__(self, "updated_at", updated_at)


@dataclass(frozen=True, slots=True)
class StoredPaperOrder(NewPaperOrder):
    """Canonical paper order including its database recording time."""

    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredPaperOrder, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))
