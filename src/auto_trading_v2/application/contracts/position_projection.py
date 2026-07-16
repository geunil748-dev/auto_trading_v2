"""Immutable PaperPosition and PositionEvent application contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
    ProjectionOutcome,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    PositionEventID,
    PositionID,
    Price,
    Quantity,
    StrategyID,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc


def _require(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{label} has an invalid type")


@dataclass(frozen=True, slots=True)
class NewPaperPosition:
    """One new OPEN position derived exclusively from a canonical BUY Fill."""

    position_id: PositionID
    strategy_id: StrategyID
    symbol: Symbol
    currency: Currency
    status: PaperPositionStatus
    quantity: Quantity
    average_cost_price: Price
    realized_pnl: Money
    opened_at: datetime
    closed_at: datetime | None
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        for value, expected, label in (
            (self.position_id, PositionID, "position_id"),
            (self.strategy_id, StrategyID, "strategy_id"),
            (self.symbol, Symbol, "symbol"),
            (self.currency, Currency, "currency"),
            (self.status, PaperPositionStatus, "status"),
            (self.quantity, Quantity, "quantity"),
            (self.average_cost_price, Price, "average_cost_price"),
            (self.realized_pnl, Money, "realized_pnl"),
        ):
            _require(value, expected, label)
        if type(self) is NewPaperPosition and self.status is not PaperPositionStatus.OPEN:
            raise ValidationError("new projected position must be OPEN")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise ValidationError("projected position version is invalid")
        closed_at = None if self.closed_at is None else normalize_utc(self.closed_at)
        if self.status is PaperPositionStatus.OPEN and (
            self.quantity.value <= 0 or closed_at is not None
        ):
            raise ValidationError("OPEN projected position state is invalid")
        if self.status is PaperPositionStatus.CLOSED and (
            self.quantity.value != 0 or closed_at is None
        ):
            raise ValidationError("CLOSED projected position state is invalid")
        if type(self) is NewPaperPosition and (
            self.quantity.value <= 0 or closed_at is not None or self.version != 1
        ):
            raise ValidationError("new projected position state is invalid")
        if self.realized_pnl.currency != self.currency:
            raise ValidationError("projected position realized P&L currency is invalid")
        if type(self) is NewPaperPosition and self.realized_pnl.amount != 0:
            raise ValidationError("new projected position realized P&L must be zero")
        opened_at = normalize_utc(self.opened_at)
        updated_at = normalize_utc(self.updated_at)
        if updated_at < opened_at:
            raise ValidationError("projected position update precedes opening")
        if type(self) is NewPaperPosition and (self.version != 1 or updated_at != opened_at):
            raise ValidationError("new projected position must start at version one")
        object.__setattr__(self, "closed_at", closed_at)
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "updated_at", updated_at)


@dataclass(frozen=True, slots=True)
class StoredPaperPosition(NewPaperPosition):
    """Canonical PaperPosition including its database recording time."""

    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredPaperPosition, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


@dataclass(frozen=True, slots=True)
class PaperPositionBuyTransition:
    """The only PaperPosition update supported by the BUY projector."""

    position_id: PositionID
    expected_version: int
    quantity: Quantity
    average_cost_price: Price
    updated_at: datetime

    def __post_init__(self) -> None:
        _require(self.position_id, PositionID, "position_id")
        _require(self.quantity, Quantity, "quantity")
        _require(self.average_cost_price, Price, "average_cost_price")
        if (
            isinstance(self.expected_version, bool)
            or not isinstance(self.expected_version, int)
            or self.expected_version <= 0
            or self.quantity.value <= 0
        ):
            raise ValidationError("position BUY transition is invalid")
        object.__setattr__(self, "updated_at", normalize_utc(self.updated_at))


@dataclass(frozen=True, slots=True)
class NewPositionEvent:
    """One immutable BUY-side change to a canonical PaperPosition."""

    position_event_id: PositionEventID
    position_id: PositionID
    fill_id: FillID
    sequence_no: int
    event_type: PositionEventType
    quantity_delta: Quantity
    quantity_after: Quantity
    average_cost_after: Price
    realized_pnl_delta: Money
    realized_pnl_after: Money
    occurred_at: datetime

    def __post_init__(self) -> None:
        for value, expected, label in (
            (self.position_event_id, PositionEventID, "position_event_id"),
            (self.position_id, PositionID, "position_id"),
            (self.fill_id, FillID, "fill_id"),
            (self.event_type, PositionEventType, "event_type"),
            (self.quantity_delta, Quantity, "quantity_delta"),
            (self.quantity_after, Quantity, "quantity_after"),
            (self.average_cost_after, Price, "average_cost_after"),
            (self.realized_pnl_delta, Money, "realized_pnl_delta"),
            (self.realized_pnl_after, Money, "realized_pnl_after"),
        ):
            _require(value, expected, label)
        if (
            isinstance(self.sequence_no, bool)
            or not isinstance(self.sequence_no, int)
            or self.sequence_no <= 0
            or self.quantity_delta.value <= 0
            or self.quantity_after.value < self.quantity_delta.value
        ):
            raise ValidationError("position event quantities or sequence are invalid")
        if (
            self.realized_pnl_delta.currency != self.realized_pnl_after.currency
            or self.realized_pnl_delta.amount != 0
        ):
            raise ValidationError("BUY position event realized P&L delta must be zero")
        object.__setattr__(self, "occurred_at", normalize_utc(self.occurred_at))


@dataclass(frozen=True, slots=True)
class StoredPositionEvent(NewPositionEvent):
    """Canonical PositionEvent including its database recording time."""

    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredPositionEvent, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


@dataclass(frozen=True, slots=True)
class PositionProjectionResult:
    """Stable result for an applied or previously applied Fill."""

    outcome: ProjectionOutcome
    fill_id: FillID
    position_id: PositionID
    position_event_id: PositionEventID
    event_type: PositionEventType
    quantity: Quantity
    average_cost_price: Price
    position_version: int

    def __post_init__(self) -> None:
        for value, expected, label in (
            (self.outcome, ProjectionOutcome, "outcome"),
            (self.fill_id, FillID, "fill_id"),
            (self.position_id, PositionID, "position_id"),
            (self.position_event_id, PositionEventID, "position_event_id"),
            (self.event_type, PositionEventType, "event_type"),
            (self.quantity, Quantity, "quantity"),
            (self.average_cost_price, Price, "average_cost_price"),
        ):
            _require(value, expected, label)
        if self.position_version <= 0:
            raise ValidationError("position_version must be positive")
