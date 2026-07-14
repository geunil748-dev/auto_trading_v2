"""Builders and read helpers for TradeIntent MSSQL tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Engine, func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidTradeIntentIDFactory
from auto_trading_v2.adapters.persistence.tables import (
    paper_fills,
    paper_orders,
    paper_positions,
)
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.application.services.trade_intent import CandidateTradeIntentService
from auto_trading_v2.domain.primitives import CandidateID, Currency, Quantity, Symbol, TradeIntentID
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide
from auto_trading_v2.domain.trade_intents.idempotency import trade_intent_idempotency_key
from tests.integration.strategy_decisions.helpers import prepare_candidate, strategy_service

CREATED_AT = datetime(2026, 7, 14, 7, tzinfo=UTC)


def prepare_decided_candidate(engine: Engine, **values: object) -> CandidateID:
    candidate_id = prepare_candidate(engine, **values)  # type: ignore[arg-type]
    strategy_service(engine).decide_all(candidate_id)
    return candidate_id


def service(engine: Engine) -> CandidateTradeIntentService:
    return CandidateTradeIntentService(
        SqlAlchemyUnitOfWorkFactory(engine),
        FixedClock(CREATED_AT),
        UuidTradeIntentIDFactory(),
    )


def decisions_for(
    engine: Engine,
    candidate_id: CandidateID,
) -> tuple[StoredCandidateStrategyDecision, ...]:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return tuple(unit_of_work.strategy_decisions.list_by_candidate(candidate_id))


def intents_for(
    engine: Engine,
    candidate_id: CandidateID,
) -> tuple[StoredTradeIntent, ...]:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        decisions = unit_of_work.strategy_decisions.list_by_candidate(candidate_id)
        intents = tuple(
            intent
            for decision in decisions
            if (intent := unit_of_work.trade_intents.get_by_decision(decision.decision_id))
            is not None
        )
    return intents


def new_intent(
    decision: StoredCandidateStrategyDecision,
    *,
    quantity: int = 40,
    idempotency_key: str | None = None,
    order_type: TradeOrderType = TradeOrderType.MARKET,
    limit_price: Decimal | None = None,
) -> NewTradeIntent:
    from auto_trading_v2.domain.primitives import Price

    return NewTradeIntent(
        trade_intent_id=TradeIntentID(uuid4()),
        decision_id=decision.decision_id,
        idempotency_key=idempotency_key or trade_intent_idempotency_key(decision.decision_id),
        symbol=Symbol("AAPL"),
        currency=Currency("USD"),
        side=TradeSide.BUY,
        order_type=order_type,
        requested_quantity=Quantity(quantity),
        limit_price=None if limit_price is None else Price(limit_price),
        time_in_force=TimeInForce.DAY,
        created_at=CREATED_AT,
    )


def persist_intent(engine: Engine, intent: NewTradeIntent) -> StoredTradeIntent:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        stored = unit_of_work.trade_intents.add(intent)
        unit_of_work.commit()
    return stored


def downstream_counts(engine: Engine) -> tuple[int, int, int]:
    with engine.connect() as connection:
        return tuple(
            int(connection.execute(select(func.count()).select_from(table)).scalar_one())
            for table in (paper_orders, paper_fills, paper_positions)
        )  # type: ignore[return-value]
