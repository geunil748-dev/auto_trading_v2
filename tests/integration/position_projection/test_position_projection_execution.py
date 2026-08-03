"""End-to-end OPENED, INCREASED, idempotency, price, and strategy cases."""

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_fills import NewPaperFill
from auto_trading_v2.application.position_projection_errors import (
    UnsupportedPositionFillSideError,
)
from auto_trading_v2.domain.position_projection import (
    PositionEventType,
    ProjectionOutcome,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    Price,
    Quantity,
    StrategyID,
)
from auto_trading_v2.domain.trade_intents import TradeSide
from tests.integration.paper_fills.helpers import EXECUTED_AT
from tests.integration.paper_fills.helpers import service as fill_service
from tests.integration.paper_orders.helpers import service as order_service
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.position_projection.helpers import (
    counts,
    event_rows,
    get_position,
    persist_custom_decision,
    position_ids,
    prepare_fill,
    scaled_candidate_values,
    service,
)
from tests.integration.strategy_decisions.helpers import prepare_candidate
from tests.integration.trade_intents.helpers import new_intent, persist_intent

pytestmark = pytest.mark.integration


def test_split_fills_open_increase_and_reapply_idempotently(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, intent, order, first_fill = prepare_fill(
        mssql_database.engine,
        quantity=41,
        strategy_id=strategy_id,
    )
    projector = service(mssql_database.engine)
    before = counts(mssql_database.engine)

    opened = projector.project_fill(first_fill.fill_id)

    assert opened.outcome is ProjectionOutcome.APPLIED
    assert opened.event_type is PositionEventType.OPENED
    assert opened.quantity == Quantity(20)
    assert opened.average_cost_price == first_fill.price
    assert opened.position_version == 1
    position_after_first = get_position(mssql_database.engine, opened.position_id)
    assert position_after_first is not None
    assert position_after_first.opened_at == first_fill.executed_at
    assert position_after_first.updated_at == first_fill.executed_at

    second_fill = fill_service(mssql_database.engine).execute_next(order.order_id).paper_fill
    increased = projector.project_fill(second_fill.fill_id)
    position_after_second = get_position(mssql_database.engine, opened.position_id)
    events = event_rows(mssql_database.engine, opened.position_id)

    assert position_after_second is not None
    assert increased.event_type is PositionEventType.INCREASED
    assert increased.position_id == opened.position_id
    assert increased.quantity == intent.requested_quantity == Quantity(41)
    assert increased.average_cost_price == first_fill.price == second_fill.price
    assert increased.position_version == position_after_second.version == 2
    assert position_after_second.opened_at == first_fill.executed_at
    assert position_after_second.updated_at == second_fill.executed_at
    assert tuple(row["sequence_no"] for row in events) == (1, 2)
    assert tuple(row["event_type"] for row in events) == ("OPENED", "INCREASED")
    assert counts(mssql_database.engine) == (before[0] + 1, before[1] + 2)

    position_before_replay = position_after_second
    event_count_before_replay = len(events)
    replay = projector.project_fill(second_fill.fill_id)

    assert replay.outcome is ProjectionOutcome.ALREADY_APPLIED
    assert get_position(mssql_database.engine, opened.position_id) == position_before_replay
    assert len(event_rows(mssql_database.engine, opened.position_id)) == event_count_before_replay


def test_different_buy_prices_use_exact_weighted_average(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, first_fill = prepare_fill(
        mssql_database.engine,
        last_price="25",
        strategy_id=strategy_id,
    )
    _, _, _, second_fill = prepare_fill(
        mssql_database.engine,
        last_price="30",
        strategy_id=strategy_id,
    )
    projector = service(mssql_database.engine)

    first = projector.project_fill(first_fill.fill_id)
    second = projector.project_fill(second_fill.fill_id)

    assert second.position_id == first.position_id
    assert second.quantity == Quantity(2)
    assert second.average_cost_price == Price(Decimal("27.500000000000000000"))
    assert second.position_version == 2


def test_same_symbol_and_currency_are_separated_by_strategy(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    first_strategy = StrategyID(uuid4())
    second_strategy = StrategyID(uuid4())
    _, _, _, first_fill = prepare_fill(
        mssql_database.engine,
        strategy_id=first_strategy,
    )
    _, _, _, second_fill = prepare_fill(
        mssql_database.engine,
        strategy_id=second_strategy,
    )
    projector = service(mssql_database.engine)

    first = projector.project_fill(first_fill.fill_id)
    second = projector.project_fill(second_fill.fill_id)

    assert first.position_id != second.position_id
    assert get_position(mssql_database.engine, first.position_id).strategy_id == first_strategy  # type: ignore[union-attr]
    assert get_position(mssql_database.engine, second.position_id).strategy_id == second_strategy  # type: ignore[union-attr]
    assert first.position_id in position_ids(mssql_database.engine)
    assert second.position_id in position_ids(mssql_database.engine)


def test_canonical_sell_fill_is_rejected_without_position_or_event(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    candidate_id = prepare_candidate(
        mssql_database.engine,
        **scaled_candidate_values("25"),
    )
    decision = persist_custom_decision(mssql_database.engine, candidate_id, strategy_id)
    sell_intent = persist_intent(
        mssql_database.engine,
        replace(new_intent(decision, quantity=1), side=TradeSide.SELL),
    )
    rejected_order = order_service(mssql_database.engine).submit(sell_intent.trade_intent_id)
    with SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work:
        candidate = unit_of_work.candidates.get(candidate_id)
        assert candidate is not None
        snapshot = unit_of_work.market_snapshots.get(candidate.market_snapshot_id)
        assert snapshot is not None
        fill = unit_of_work.paper_fills.add(
            NewPaperFill(
                fill_id=FillID(uuid4()),
                order_id=rejected_order.order_id,
                execution_key=f"sell-projection-test-{uuid4().hex}",
                fill_sequence=1,
                quantity=Quantity(1),
                price=snapshot.last_price,
                fee=Money(Decimal("0"), Currency("USD")),
                executed_at=EXECUTED_AT,
            )
        )
        unit_of_work.commit()
    before = counts(mssql_database.engine)

    with pytest.raises(UnsupportedPositionFillSideError):
        service(mssql_database.engine).project_fill(fill.fill_id)

    assert counts(mssql_database.engine) == before
