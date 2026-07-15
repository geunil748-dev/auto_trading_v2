"""SQLAlchemy Core repository for immutable canonical PaperFills."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import paper_fills
from auto_trading_v2.application.contracts.paper_fills import NewPaperFill, StoredPaperFill
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import Currency, FillID, Money, OrderID, Price, Quantity


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


def map_paper_fill(row: Mapping[Any, Any]) -> StoredPaperFill:
    """Map one row without exposing raw stored values on failure."""

    required = (
        "fill_id",
        "order_id",
        "execution_key",
        "fill_sequence",
        "quantity",
        "price",
        "fee_amount",
        "fee_currency",
        "executed_at",
        "recorded_at",
    )
    try:
        if any(row[name] is None for name in required):
            raise TypeError
        return StoredPaperFill(
            fill_id=FillID(_uuid(row["fill_id"])),
            order_id=OrderID(_uuid(row["order_id"])),
            execution_key=str(row["execution_key"]),
            fill_sequence=_integer(row["fill_sequence"]),
            quantity=Quantity(_integer(row["quantity"])),
            price=Price(_decimal(row["price"])),
            fee=Money(_decimal(row["fee_amount"]), Currency(str(row["fee_currency"]))),
            executed_at=_datetime(row["executed_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("paper_fill") from None


class SqlAlchemyPaperFillRepository:
    """Persist immutable fills only inside a caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, paper_fill: NewPaperFill) -> StoredPaperFill:
        self._ensure_active()
        try:
            self._connection.execute(
                paper_fills.insert().values(
                    fill_id=paper_fill.fill_id.value,
                    order_id=paper_fill.order_id.value,
                    execution_key=paper_fill.execution_key,
                    fill_sequence=paper_fill.fill_sequence,
                    quantity=paper_fill.quantity.value,
                    price=paper_fill.price.value,
                    fee_amount=paper_fill.fee.amount,
                    fee_currency=paper_fill.fee.currency.code,
                    executed_at=paper_fill.executed_at,
                )
            )
            stored = self._select_one(paper_fills.c.fill_id == paper_fill.fill_id.value)
            if stored is None:
                raise PersistenceMappingError("paper_fill", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_fill", operation="insert"
            ) from None

    def get(self, fill_id: FillID) -> StoredPaperFill | None:
        return self._read(lambda: self._select_one(paper_fills.c.fill_id == fill_id.value))

    def get_by_execution_key(self, execution_key: str) -> StoredPaperFill | None:
        return self._read(lambda: self._select_one(paper_fills.c.execution_key == execution_key))

    def get_by_order_sequence(
        self, *, order_id: OrderID, fill_sequence: int
    ) -> StoredPaperFill | None:
        return self._read(
            lambda: self._select_one(
                (paper_fills.c.order_id == order_id.value)
                & (paper_fills.c.fill_sequence == fill_sequence)
            )
        )

    def list_by_order(self, order_id: OrderID) -> Sequence[StoredPaperFill]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(paper_fills)
                    .where(paper_fills.c.order_id == order_id.value)
                    .order_by(paper_fills.c.fill_sequence, paper_fills.c.fill_id)
                )
                .mappings()
                .all()
            )
            return tuple(map_paper_fill(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_fill", operation="select"
            ) from None

    def _read(self, operation: Callable[[], StoredPaperFill | None]) -> StoredPaperFill | None:
        self._ensure_active()
        try:
            return operation()
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_fill", operation="select"
            ) from None

    def _select_one(self, predicate: ColumnElement[bool]) -> StoredPaperFill | None:
        row = (
            self._connection.execute(select(paper_fills).where(predicate)).mappings().one_or_none()
        )
        return None if row is None else map_paper_fill(row)
