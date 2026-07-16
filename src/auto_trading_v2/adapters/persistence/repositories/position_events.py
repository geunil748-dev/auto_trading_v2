"""SQLAlchemy Core repository for immutable canonical PositionEvents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import paper_positions, position_events
from auto_trading_v2.application.contracts.position_projection import (
    NewPositionEvent,
    StoredPositionEvent,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.position_projection import PositionEventType
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    PositionEventID,
    PositionID,
    Price,
    Quantity,
)


def _allow_operation() -> None:
    return None


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def map_position_event(row: Mapping[Any, Any]) -> StoredPositionEvent:
    """Map one joined event row without exposing raw stored values."""

    required = (
        "position_event_id",
        "position_id",
        "fill_id",
        "sequence_no",
        "event_type",
        "quantity_delta",
        "quantity_after",
        "average_cost_after",
        "realized_pnl_delta",
        "realized_pnl_after",
        "occurred_at",
        "recorded_at",
        "_position_currency",
    )
    try:
        if any(row[name] is None for name in required):
            raise TypeError
        currency = Currency(str(row["_position_currency"]))
        return StoredPositionEvent(
            position_event_id=PositionEventID(_uuid(row["position_event_id"])),
            position_id=PositionID(_uuid(row["position_id"])),
            fill_id=FillID(_uuid(row["fill_id"])),
            sequence_no=_integer(row["sequence_no"]),
            event_type=PositionEventType(str(row["event_type"])),
            quantity_delta=Quantity(_integer(row["quantity_delta"])),
            quantity_after=Quantity(_integer(row["quantity_after"])),
            average_cost_after=Price(_decimal(row["average_cost_after"])),
            realized_pnl_delta=Money(_decimal(row["realized_pnl_delta"]), currency),
            realized_pnl_after=Money(_decimal(row["realized_pnl_after"]), currency),
            occurred_at=_datetime(row["occurred_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("position_event") from None


class SqlAlchemyPositionEventRepository:
    """Append PositionEvents only inside the caller's transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, event: NewPositionEvent) -> StoredPositionEvent:
        self._ensure_active()
        try:
            self._connection.execute(
                position_events.insert().values(
                    position_event_id=event.position_event_id.value,
                    position_id=event.position_id.value,
                    fill_id=event.fill_id.value,
                    sequence_no=event.sequence_no,
                    event_type=event.event_type.value,
                    quantity_delta=event.quantity_delta.value,
                    quantity_after=event.quantity_after.value,
                    average_cost_after=event.average_cost_after.value,
                    realized_pnl_delta=event.realized_pnl_delta.amount,
                    realized_pnl_after=event.realized_pnl_after.amount,
                    occurred_at=event.occurred_at,
                )
            )
            stored = self._select_one(
                position_events.c.position_event_id == event.position_event_id.value
            )
            if stored is None:
                raise PersistenceMappingError("position_event", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="position_event", operation="insert"
            ) from None

    def get(self, position_event_id: PositionEventID) -> StoredPositionEvent | None:
        return self._read(
            lambda: self._select_one(position_events.c.position_event_id == position_event_id.value)
        )

    def get_by_fill_id(self, fill_id: FillID) -> StoredPositionEvent | None:
        return self._read(lambda: self._select_one(position_events.c.fill_id == fill_id.value))

    def _read(
        self, operation: Callable[[], StoredPositionEvent | None]
    ) -> StoredPositionEvent | None:
        self._ensure_active()
        try:
            return operation()
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="position_event", operation="select"
            ) from None

    def _select_one(self, predicate: ColumnElement[bool]) -> StoredPositionEvent | None:
        statement = (
            select(
                position_events,
                paper_positions.c.currency.label("_position_currency"),
            )
            .select_from(
                position_events.join(
                    paper_positions,
                    position_events.c.position_id == paper_positions.c.position_id,
                )
            )
            .where(predicate)
        )
        row = self._connection.execute(statement).mappings().one_or_none()
        return None if row is None else map_position_event(row)
