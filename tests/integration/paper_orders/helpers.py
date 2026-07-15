"""Builders and read helpers for PaperOrder MSSQL tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, func, select

from auto_trading_v2.adapters.brokers import InternalPaperBroker
from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import (
    Uuid5ClientOrderIDFactory,
    UuidOrderIDFactory,
)
from auto_trading_v2.adapters.persistence.tables import paper_fills, paper_orders, paper_positions
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_orders import NewPaperOrder, StoredPaperOrder
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.services.paper_order import PaperOrderSubmissionService
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import ClientOrderID, OrderID

SUBMITTED_AT = datetime(2026, 7, 15, 2, tzinfo=UTC)


def service(
    engine: Engine, broker: InternalPaperBroker | None = None
) -> PaperOrderSubmissionService:
    return PaperOrderSubmissionService(
        SqlAlchemyUnitOfWorkFactory(engine),
        FixedClock(SUBMITTED_AT),
        UuidOrderIDFactory(),
        Uuid5ClientOrderIDFactory(),
        broker or InternalPaperBroker(),
    )


def new_order(
    intent: StoredTradeIntent,
    *,
    status: PaperOrderStatus = PaperOrderStatus.ACCEPTED,
    client_order_id: ClientOrderID | None = None,
    broker_order_ref: str | None = None,
) -> NewPaperOrder:
    accepted = status is PaperOrderStatus.ACCEPTED
    return NewPaperOrder(
        order_id=OrderID(uuid4()),
        trade_intent_id=intent.trade_intent_id,
        client_order_id=client_order_id or ClientOrderID(uuid4()),
        broker_code="INTERNAL_PAPER",
        broker_order_ref=broker_order_ref or f"internal-paper:v1:{uuid4()}",
        status=status,
        rejection_code=None if accepted else "UNSUPPORTED_SIDE",
        submitted_at=SUBMITTED_AT,
        accepted_at=SUBMITTED_AT if accepted else None,
        closed_at=None if accepted else SUBMITTED_AT,
        version=1,
        updated_at=SUBMITTED_AT,
    )


def get_order(engine: Engine, order_id: OrderID) -> StoredPaperOrder | None:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return unit_of_work.paper_orders.get(order_id)


def downstream_counts(engine: Engine) -> tuple[int, int, int]:
    with engine.connect() as connection:
        return tuple(
            int(connection.execute(select(func.count()).select_from(table)).scalar_one())
            for table in (paper_orders, paper_fills, paper_positions)
        )  # type: ignore[return-value]
