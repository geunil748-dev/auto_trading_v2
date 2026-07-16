"""Canonical pipeline builders and reads for Position Projector tests."""

from __future__ import annotations

from decimal import Decimal, localcontext
from uuid import uuid4

from sqlalchemy import Engine, func, select

from auto_trading_v2.adapters.identifiers import (
    UuidPositionEventIDFactory,
    UuidPositionIDFactory,
)
from auto_trading_v2.adapters.persistence.tables import paper_positions, position_events
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_fills import StoredPaperFill
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.position_projection import (
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.services.position_projector import PositionProjectorService
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FillID,
    PositionID,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions import StrategyAction
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.paper_fills.helpers import service as fill_service
from tests.integration.paper_orders.helpers import service as order_service
from tests.integration.strategy_decisions.helpers import DECIDED_AT, prepare_candidate
from tests.integration.trade_intents.helpers import (
    decisions_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
)


def service(engine: Engine) -> PositionProjectorService:
    return PositionProjectorService(
        SqlAlchemyUnitOfWorkFactory(engine),
        UuidPositionIDFactory(),
        UuidPositionEventIDFactory(),
    )


def scaled_candidate_values(last_price: str) -> dict[str, str]:
    with localcontext() as context:
        context.prec = 38
        factor = Decimal(last_price) / Decimal("25")
        return {
            "open_price": str(Decimal("22.66") * factor),
            "last_price": last_price,
            "previous_high": str(Decimal("20") * factor),
            "previous_low": str(Decimal("10") * factor),
            "previous_close": str(Decimal("22") * factor),
        }


def prepare_fill(
    engine: Engine,
    *,
    quantity: int = 1,
    last_price: str = "25",
    decision_index: int = 0,
    strategy_id: StrategyID | None = None,
) -> tuple[CandidateID, StoredTradeIntent, StoredPaperOrder, StoredPaperFill]:
    if strategy_id is None:
        candidate_id = prepare_decided_candidate(engine, **scaled_candidate_values(last_price))
        decision = decisions_for(engine, candidate_id)[decision_index]
    else:
        candidate_id = prepare_candidate(engine, **scaled_candidate_values(last_price))
        decision = persist_custom_decision(engine, candidate_id, strategy_id)
    intent = persist_intent(engine, new_intent(decision, quantity=quantity))
    order = order_service(engine).submit(intent.trade_intent_id)
    fill = fill_service(engine).execute_next(order.order_id).paper_fill
    return candidate_id, intent, order, fill


def persist_custom_decision(
    engine: Engine,
    candidate_id: CandidateID,
    strategy_id: StrategyID,
) -> StoredCandidateStrategyDecision:
    evaluation = evaluations_for(engine, candidate_id)[0]
    value = NewCandidateStrategyDecision(
        decision_id=DecisionID(uuid4()),
        decision_key=f"candidate:{candidate_id}|strategy:{strategy_id}|version:v1",
        candidate_id=candidate_id,
        filter_evaluation_id=evaluation.filter_evaluation_id,
        strategy_id=strategy_id,
        strategy_version="v1",
        action=StrategyAction.ENTER_LONG,
        reason_codes=("ENTRY_ALLOWED",),
        decided_at=DECIDED_AT,
    )
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        stored = unit_of_work.strategy_decisions.add(value)
        unit_of_work.commit()
    return stored


def get_position(engine: Engine, position_id: PositionID) -> StoredPaperPosition | None:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return unit_of_work.paper_positions.get(position_id)


def get_event(engine: Engine, fill_id: FillID) -> StoredPositionEvent | None:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return unit_of_work.position_events.get_by_fill_id(fill_id)


def counts(engine: Engine) -> tuple[int, int]:
    with engine.connect() as connection:
        return tuple(
            int(connection.execute(select(func.count()).select_from(table)).scalar_one())
            for table in (paper_positions, position_events)
        )  # type: ignore[return-value]


def position_ids(engine: Engine) -> tuple[PositionID, ...]:
    with engine.connect() as connection:
        values = connection.execute(
            select(paper_positions.c.position_id).order_by(paper_positions.c.position_id)
        ).scalars()
        return tuple(PositionID(value) for value in values)


def event_rows(engine: Engine, position_id: PositionID) -> tuple[object, ...]:
    with engine.connect() as connection:
        return tuple(
            connection.execute(
                select(position_events)
                .where(position_events.c.position_id == position_id.value)
                .order_by(position_events.c.sequence_no)
            )
            .mappings()
            .all()
        )
