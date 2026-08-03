"""SQLAlchemy Core repository for canonical PaperPosition current state."""

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
from auto_trading_v2.adapters.persistence.tables import paper_positions
from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    PaperPositionBuyTransition,
    StoredPaperPosition,
)
from auto_trading_v2.application.errors import (
    OptimisticConcurrencyError,
    PersistenceMappingError,
    PersistenceNotFoundError,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.position_projection import PaperPositionStatus
from auto_trading_v2.domain.primitives import (
    Currency,
    Money,
    PositionID,
    Price,
    Quantity,
    StrategyID,
    Symbol,
)


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


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def map_paper_position(row: Mapping[Any, Any]) -> StoredPaperPosition:
    """Map one position row without echoing raw stored values on failure."""

    required = (
        "position_id",
        "strategy_id",
        "symbol",
        "currency",
        "status",
        "quantity",
        "average_cost_price",
        "realized_pnl_amount",
        "opened_at",
        "version",
        "recorded_at",
        "updated_at",
    )
    try:
        if any(row[name] is None for name in required):
            raise TypeError
        currency = Currency(str(row["currency"]))
        return StoredPaperPosition(
            position_id=PositionID(_uuid(row["position_id"])),
            strategy_id=StrategyID(_uuid(row["strategy_id"])),
            symbol=Symbol(str(row["symbol"])),
            currency=currency,
            status=PaperPositionStatus(str(row["status"])),
            quantity=Quantity(_integer(row["quantity"])),
            average_cost_price=Price(_decimal(row["average_cost_price"])),
            realized_pnl=Money(_decimal(row["realized_pnl_amount"]), currency),
            opened_at=_datetime(row["opened_at"]),
            closed_at=_optional_datetime(row["closed_at"]),
            version=_integer(row["version"]),
            recorded_at=_datetime(row["recorded_at"]),
            updated_at=_datetime(row["updated_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("paper_position") from None


class SqlAlchemyPaperPositionRepository:
    """Create or optimistically increase positions in a caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, position: NewPaperPosition) -> StoredPaperPosition:
        self._ensure_active()
        try:
            self._connection.execute(
                paper_positions.insert().values(
                    position_id=position.position_id.value,
                    strategy_id=position.strategy_id.value,
                    symbol=position.symbol.value,
                    currency=position.currency.code,
                    status=position.status.value,
                    quantity=position.quantity.value,
                    average_cost_price=position.average_cost_price.value,
                    realized_pnl_amount=position.realized_pnl.amount,
                    opened_at=position.opened_at,
                    closed_at=position.closed_at,
                    version=position.version,
                    updated_at=position.updated_at,
                )
            )
            stored = self._select_one(paper_positions.c.position_id == position.position_id.value)
            if stored is None:
                raise PersistenceMappingError("paper_position", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_position", operation="insert"
            ) from None

    def get(self, position_id: PositionID) -> StoredPaperPosition | None:
        return self._read(
            lambda: self._select_one(paper_positions.c.position_id == position_id.value)
        )

    def get_open_by_key(
        self,
        *,
        strategy_id: StrategyID,
        symbol: Symbol,
        currency: Currency,
    ) -> StoredPaperPosition | None:
        return self._read(
            lambda: self._select_one(
                (paper_positions.c.strategy_id == strategy_id.value)
                & (paper_positions.c.symbol == symbol.value)
                & (paper_positions.c.currency == currency.code)
                & (paper_positions.c.status == PaperPositionStatus.OPEN.value)
            )
        )

    def transition_after_buy_fill(
        self,
        transition: PaperPositionBuyTransition,
    ) -> StoredPaperPosition:
        self._ensure_active()
        try:
            result = self._connection.execute(
                paper_positions.update()
                .where(
                    paper_positions.c.position_id == transition.position_id.value,
                    paper_positions.c.status == PaperPositionStatus.OPEN.value,
                    paper_positions.c.version == transition.expected_version,
                )
                .values(
                    quantity=transition.quantity.value,
                    average_cost_price=transition.average_cost_price.value,
                    updated_at=transition.updated_at,
                    version=transition.expected_version + 1,
                )
            )
            if result.rowcount != 1:
                current = self._select_one(
                    paper_positions.c.position_id == transition.position_id.value
                )
                self._mark_failed()
                if current is None:
                    raise PersistenceNotFoundError(
                        entity="paper_position",
                        operation="transition_after_buy_fill",
                        reason="not_found",
                    )
                raise OptimisticConcurrencyError(
                    entity="paper_position",
                    operation="transition_after_buy_fill",
                    reason="stale_status_or_version",
                )
            stored = self._select_one(paper_positions.c.position_id == transition.position_id.value)
            if stored is None:
                raise PersistenceMappingError("paper_position", "transition_after_buy_fill")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="paper_position",
                operation="transition_after_buy_fill",
            ) from None

    def _read(
        self, operation: Callable[[], StoredPaperPosition | None]
    ) -> StoredPaperPosition | None:
        self._ensure_active()
        try:
            return operation()
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="paper_position", operation="select"
            ) from None

    def _select_one(self, predicate: ColumnElement[bool]) -> StoredPaperPosition | None:
        row = (
            self._connection.execute(select(paper_positions).where(predicate))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_paper_position(row)
