"""SQLAlchemy Core repository for canonical trade intents."""

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
from auto_trading_v2.adapters.persistence.tables import trade_intents
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    Currency,
    DecisionID,
    Price,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.trade_intents.models import (
    TimeInForce,
    TradeOrderType,
    TradeSide,
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


def map_trade_intent(row: Mapping[Any, Any]) -> StoredTradeIntent:
    """Map one row to an immutable contract without exposing raw values."""

    required = (
        "trade_intent_id",
        "decision_id",
        "idempotency_key",
        "symbol",
        "currency",
        "side",
        "order_type",
        "requested_quantity",
        "time_in_force",
        "created_at",
        "recorded_at",
    )
    try:
        if any(row[name] is None for name in required):
            raise TypeError
        raw_limit = row["limit_price"]
        return StoredTradeIntent(
            trade_intent_id=TradeIntentID(_uuid(row["trade_intent_id"])),
            decision_id=DecisionID(_uuid(row["decision_id"])),
            idempotency_key=str(row["idempotency_key"]),
            symbol=Symbol(str(row["symbol"])),
            currency=Currency(str(row["currency"])),
            side=TradeSide(str(row["side"])),
            order_type=TradeOrderType(str(row["order_type"])),
            requested_quantity=Quantity(_integer(row["requested_quantity"])),
            limit_price=None if raw_limit is None else Price(_decimal(raw_limit)),
            time_in_force=TimeInForce(str(row["time_in_force"])),
            created_at=_datetime(row["created_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("trade_intent") from None


class SqlAlchemyTradeIntentRepository:
    """Persist trade intents only inside a caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, trade_intent: NewTradeIntent) -> StoredTradeIntent:
        self._ensure_active()
        try:
            self._connection.execute(
                trade_intents.insert().values(
                    trade_intent_id=trade_intent.trade_intent_id.value,
                    decision_id=trade_intent.decision_id.value,
                    idempotency_key=trade_intent.idempotency_key,
                    symbol=trade_intent.symbol.value,
                    currency=trade_intent.currency.code,
                    side=trade_intent.side.value,
                    order_type=trade_intent.order_type.value,
                    requested_quantity=trade_intent.requested_quantity.value,
                    limit_price=(
                        None if trade_intent.limit_price is None else trade_intent.limit_price.value
                    ),
                    time_in_force=trade_intent.time_in_force.value,
                    created_at=trade_intent.created_at,
                )
            )
            stored = self._select_by_id(trade_intent.trade_intent_id)
            if stored is None:
                raise PersistenceMappingError("trade_intent", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="trade_intent",
                operation="insert",
            ) from None

    def get(self, trade_intent_id: TradeIntentID) -> StoredTradeIntent | None:
        return self._read(lambda: self._select_by_id(trade_intent_id))

    def get_by_decision(self, decision_id: DecisionID) -> StoredTradeIntent | None:
        return self._read(
            lambda: self._select_one(trade_intents.c.decision_id == decision_id.value)
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> StoredTradeIntent | None:
        return self._read(
            lambda: self._select_one(trade_intents.c.idempotency_key == idempotency_key)
        )

    def _read(self, operation: Callable[[], StoredTradeIntent | None]) -> StoredTradeIntent | None:
        self._ensure_active()
        try:
            return operation()
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="trade_intent",
                operation="select",
            ) from None

    def _select_by_id(self, trade_intent_id: TradeIntentID) -> StoredTradeIntent | None:
        return self._select_one(trade_intents.c.trade_intent_id == trade_intent_id.value)

    def _select_one(self, predicate: ColumnElement[bool]) -> StoredTradeIntent | None:
        row = (
            self._connection.execute(select(trade_intents).where(predicate))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_trade_intent(row)
