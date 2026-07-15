"""SQLAlchemy Core repository for canonical paper orders."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import paper_orders
from auto_trading_v2.application.contracts.paper_orders import NewPaperOrder, StoredPaperOrder
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import ClientOrderID, OrderID, TradeIntentID


def _allow_operation() -> None:
    return None


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def map_paper_order(row: Mapping[Any, Any]) -> StoredPaperOrder:
    """Map one row without exposing raw stored values on failure."""

    required = (
        "order_id",
        "trade_intent_id",
        "client_order_id",
        "broker_code",
        "status",
        "submitted_at",
        "version",
        "recorded_at",
        "updated_at",
    )
    try:
        if any(row[name] is None for name in required):
            raise TypeError
        return StoredPaperOrder(
            order_id=OrderID(_uuid(row["order_id"])),
            trade_intent_id=TradeIntentID(_uuid(row["trade_intent_id"])),
            client_order_id=ClientOrderID(_uuid(row["client_order_id"])),
            broker_code=str(row["broker_code"]),
            broker_order_ref=_optional_string(row["broker_order_ref"]),
            status=PaperOrderStatus(str(row["status"])),
            rejection_code=_optional_string(row["rejection_code"]),
            submitted_at=_datetime(row["submitted_at"]),
            accepted_at=_optional_datetime(row["accepted_at"]),
            closed_at=_optional_datetime(row["closed_at"]),
            version=_integer(row["version"]),
            recorded_at=_datetime(row["recorded_at"]),
            updated_at=_datetime(row["updated_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("paper_order") from None


class SqlAlchemyPaperOrderRepository:
    """Persist paper orders only inside a caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, paper_order: NewPaperOrder) -> StoredPaperOrder:
        self._ensure_active()
        try:
            self._connection.execute(
                paper_orders.insert().values(
                    order_id=paper_order.order_id.value,
                    trade_intent_id=paper_order.trade_intent_id.value,
                    client_order_id=paper_order.client_order_id.value,
                    broker_code=paper_order.broker_code,
                    broker_order_ref=paper_order.broker_order_ref,
                    status=paper_order.status.value,
                    rejection_code=paper_order.rejection_code,
                    submitted_at=paper_order.submitted_at,
                    accepted_at=paper_order.accepted_at,
                    closed_at=paper_order.closed_at,
                    version=paper_order.version,
                    updated_at=paper_order.updated_at,
                )
            )
            stored = self._select_one(paper_orders.c.order_id == paper_order.order_id.value)
            if stored is None:
                raise PersistenceMappingError("paper_order", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_order", operation="insert"
            ) from None

    def get(self, order_id: OrderID) -> StoredPaperOrder | None:
        return self._read(lambda: self._select_one(paper_orders.c.order_id == order_id.value))

    def get_by_trade_intent(self, trade_intent_id: TradeIntentID) -> StoredPaperOrder | None:
        return self._read(
            lambda: self._select_one(paper_orders.c.trade_intent_id == trade_intent_id.value)
        )

    def get_by_client_order_id(self, client_order_id: ClientOrderID) -> StoredPaperOrder | None:
        return self._read(
            lambda: self._select_one(paper_orders.c.client_order_id == client_order_id.value)
        )

    def get_by_broker_reference(
        self, *, broker_code: str, broker_order_ref: str
    ) -> StoredPaperOrder | None:
        return self._read(
            lambda: self._select_one(
                (paper_orders.c.broker_code == broker_code)
                & (paper_orders.c.broker_order_ref == broker_order_ref)
            )
        )

    def _read(self, operation: Callable[[], StoredPaperOrder | None]) -> StoredPaperOrder | None:
        self._ensure_active()
        try:
            return operation()
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_order", operation="select"
            ) from None

    def _select_one(self, predicate: ColumnElement[bool]) -> StoredPaperOrder | None:
        row = (
            self._connection.execute(select(paper_orders).where(predicate)).mappings().one_or_none()
        )
        return None if row is None else map_paper_order(row)
