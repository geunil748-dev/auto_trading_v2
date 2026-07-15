"""Canonical pipeline builders and read helpers for PaperFill MSSQL tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Engine, func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidFillIDFactory
from auto_trading_v2.adapters.persistence.tables import (
    equity_snapshots,
    paper_fills,
    paper_positions,
    position_events,
)
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_fills import StoredPaperFill
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.services.paper_fill import PaperFillExecutionService
from auto_trading_v2.domain.primitives import CandidateID, OrderID
from tests.integration.paper_orders.helpers import service as paper_order_service
from tests.integration.trade_intents.helpers import (
    decisions_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
)
from tests.integration.trade_intents.helpers import service as trade_intent_service

EXECUTED_AT = datetime(2026, 7, 15, 4, tzinfo=UTC)


def service(engine: Engine) -> PaperFillExecutionService:
    return PaperFillExecutionService(
        SqlAlchemyUnitOfWorkFactory(engine),
        FixedClock(EXECUTED_AT),
        UuidFillIDFactory(),
    )


def prepare_order(
    engine: Engine,
    *,
    quantity: int = 40,
    last_price: str = "25",
) -> tuple[StoredTradeIntent, StoredPaperOrder]:
    candidate_id = prepare_decided_candidate(
        engine,
        open_price="22.66",
        last_price=last_price,
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )
    source_intent = persist_intent(
        engine,
        new_intent(decisions_for(engine, candidate_id)[0], quantity=quantity),
    )
    source_order = paper_order_service(engine).submit(source_intent.trade_intent_id)
    return source_intent, source_order


def prepare_case_orders(
    engine: Engine,
    **values: object,
) -> tuple[CandidateID, tuple[StoredTradeIntent, ...], tuple[StoredPaperOrder, ...]]:
    candidate_id = prepare_decided_candidate(engine, **values)
    intents = trade_intent_service(engine).create_all(candidate_id).trade_intents
    orders = tuple(paper_order_service(engine).submit(intent.trade_intent_id) for intent in intents)
    return candidate_id, tuple(intents), orders


def get_order(engine: Engine, order_id: OrderID) -> StoredPaperOrder | None:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return unit_of_work.paper_orders.get(order_id)


def fills_for(engine: Engine, order_id: OrderID) -> tuple[StoredPaperFill, ...]:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return tuple(unit_of_work.paper_fills.list_by_order(order_id))


def projector_counts(engine: Engine) -> tuple[int, int, int]:
    with engine.connect() as connection:
        return tuple(
            int(connection.execute(select(func.count()).select_from(table)).scalar_one())
            for table in (paper_positions, position_events, equity_snapshots)
        )  # type: ignore[return-value]


def total_fill_quantity(fills: tuple[StoredPaperFill, ...]) -> int:
    return sum(item.quantity.value for item in fills)


def average_price_not_stored() -> bool:
    return "average_price" not in paper_fills.c and "cumulative_quantity" not in paper_fills.c


def exact_decimal(value: str) -> Decimal:
    return Decimal(value)
