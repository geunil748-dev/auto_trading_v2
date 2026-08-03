"""Canonical pipeline and snapshot builders for position exit integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Engine, func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDecisionIDFactory
from auto_trading_v2.adapters.persistence.tables import (
    paper_fills,
    paper_orders,
    paper_positions,
    position_events,
    strategy_decisions,
    trade_intents,
)
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.persistence import NewMarketSnapshot
from auto_trading_v2.application.contracts.position_projection import (
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.services.position_exit_decision import (
    PositionExitDecisionService,
)
from auto_trading_v2.domain.primitives import (
    MarketSnapshotID,
    PositionID,
    Price,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.strategy_decisions.catalog import SCORE_ONLY_ENTRY
from tests.integration.position_projection.helpers import (
    get_event,
    get_position,
    prepare_fill,
)
from tests.integration.position_projection.helpers import service as projector_service


@dataclass(frozen=True, slots=True)
class PreparedPosition:
    position: StoredPaperPosition
    event: StoredPositionEvent


def prepare_position(engine: Engine) -> PreparedPosition:
    _, _, _, fill = prepare_fill(
        engine,
        quantity=10,
        last_price="100",
        strategy_id=SCORE_ONLY_ENTRY.strategy_id,
    )
    projected = projector_service(engine).project_fill(fill.fill_id)
    position = get_position(engine, projected.position_id)
    event = get_event(engine, fill.fill_id)
    assert position is not None
    assert event is not None
    return PreparedPosition(position, event)


def add_snapshot(
    engine: Engine,
    *,
    observed_at: datetime,
    last_price: str,
    symbol: str = "AAPL",
) -> MarketSnapshotID:
    price = Price(Decimal(last_price))
    snapshot = NewMarketSnapshot(
        market_snapshot_id=MarketSnapshotID(uuid4()),
        symbol=Symbol(symbol),
        session_date=SessionDate(observed_at.date()),
        observed_at=observed_at,
        source=f"POSITION_EXIT_{uuid4().hex}",
        open_price=price,
        high_price=price,
        low_price=price,
        last_price=price,
        previous_high_price=price,
        previous_low_price=price,
        previous_close_price=price,
        volume=1,
    )
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        unit_of_work.market_snapshots.add(snapshot)
        unit_of_work.commit()
    return snapshot.market_snapshot_id


def service(engine: Engine, now: datetime) -> PositionExitDecisionService:
    return PositionExitDecisionService(
        SqlAlchemyUnitOfWorkFactory(engine),
        FixedClock(now),
        UuidDecisionIDFactory(),
    )


def decisions_for(
    engine: Engine,
    position_id: PositionID,
) -> tuple[StoredPositionStrategyDecision, ...]:
    with engine.connect() as connection:
        rows = (
            connection.execute(
                select(strategy_decisions)
                .where(strategy_decisions.c.position_id == position_id.value)
                .order_by(strategy_decisions.c.decided_at, strategy_decisions.c.decision_id)
            )
            .mappings()
            .all()
        )
    from auto_trading_v2.adapters.persistence.strategy_decision_mapping import (
        map_position_strategy_decision,
    )

    return tuple(map_position_strategy_decision(row) for row in rows)


def source_counts(engine: Engine) -> tuple[int, int, int, int, int]:
    with engine.connect() as connection:
        return tuple(
            int(connection.execute(select(func.count()).select_from(table)).scalar_one())
            for table in (
                paper_positions,
                position_events,
                paper_fills,
                paper_orders,
                trade_intents,
            )
        )  # type: ignore[return-value]


def position_row(engine: Engine, position_id: PositionID) -> object:
    with engine.connect() as connection:
        return (
            connection.execute(
                select(paper_positions).where(paper_positions.c.position_id == position_id.value)
            )
            .mappings()
            .one()
        )
