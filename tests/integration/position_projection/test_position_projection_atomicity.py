"""Real MSSQL rollback, stale-version, and competing-Fill guarantees."""

from decimal import Decimal
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
)
from auto_trading_v2.application.errors import (
    ForeignKeyViolationError,
    OptimisticConcurrencyError,
)
from auto_trading_v2.application.position_projection_errors import (
    PositionProjectionConcurrencyError,
)
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    PositionEventID,
    PositionID,
    Price,
    Quantity,
    StrategyID,
    Symbol,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.position_projection.helpers import (
    get_event,
    get_position,
    prepare_fill,
    service,
)

pytestmark = pytest.mark.integration


def new_position(
    *,
    position_id: PositionID,
    strategy_id: StrategyID,
    occurred_at,
    quantity: int = 1,
    average: str = "25",
) -> NewPaperPosition:
    return NewPaperPosition(
        position_id=position_id,
        strategy_id=strategy_id,
        symbol=Symbol("AAPL"),
        currency=Currency("USD"),
        status=PaperPositionStatus.OPEN,
        quantity=Quantity(quantity),
        average_cost_price=Price(Decimal(average)),
        realized_pnl=Money(Decimal("0"), Currency("USD")),
        opened_at=occurred_at,
        closed_at=None,
        version=1,
        updated_at=occurred_at,
    )


def new_event(
    *,
    position_id: PositionID,
    fill_id: FillID,
    sequence: int,
    quantity_delta: int,
    quantity_after: int,
    average: str,
    occurred_at,
) -> NewPositionEvent:
    return NewPositionEvent(
        position_event_id=PositionEventID(uuid4()),
        position_id=position_id,
        fill_id=fill_id,
        sequence_no=sequence,
        event_type=(PositionEventType.OPENED if sequence == 1 else PositionEventType.INCREASED),
        quantity_delta=Quantity(quantity_delta),
        quantity_after=Quantity(quantity_after),
        average_cost_after=Price(Decimal(average)),
        realized_pnl_delta=Money(Decimal("0"), Currency("USD")),
        realized_pnl_after=Money(Decimal("0"), Currency("USD")),
        occurred_at=occurred_at,
    )


def test_new_position_rolls_back_when_event_fk_insert_fails(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    position_id = PositionID(uuid4())
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work, pytest.raises(ForeignKeyViolationError):
        unit_of_work.paper_positions.add(
            new_position(
                position_id=position_id,
                strategy_id=strategy_id,
                occurred_at=fill.executed_at,
            )
        )
        unit_of_work.position_events.add(
            new_event(
                position_id=position_id,
                fill_id=FillID(uuid4()),
                sequence=1,
                quantity_delta=1,
                quantity_after=1,
                average="25",
                occurred_at=fill.executed_at,
            )
        )
        unit_of_work.commit()

    assert get_position(mssql_database.engine, position_id) is None


def test_stale_update_rolls_back_new_event_and_fill_can_retry(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, first_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    opened = service(mssql_database.engine).project_fill(first_fill.fill_id)
    _, _, _, second_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    position_before = get_position(mssql_database.engine, opened.position_id)
    assert position_before is not None and position_before.version == 1
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work, pytest.raises(OptimisticConcurrencyError):
        unit_of_work.position_events.add(
            new_event(
                position_id=opened.position_id,
                fill_id=second_fill.fill_id,
                sequence=2,
                quantity_delta=1,
                quantity_after=2,
                average="25",
                occurred_at=second_fill.executed_at,
            )
        )
        unit_of_work.paper_positions.transition_after_buy_fill(
            PaperPositionBuyTransition(
                position_id=opened.position_id,
                expected_version=2,
                quantity=Quantity(2),
                average_cost_price=Price(Decimal("25")),
                updated_at=second_fill.executed_at,
            )
        )
        unit_of_work.commit()

    assert get_event(mssql_database.engine, second_fill.fill_id) is None
    assert get_position(mssql_database.engine, opened.position_id) == position_before
    retried = service(mssql_database.engine).project_fill(second_fill.fill_id)
    assert retried.position_version == 2
    assert retried.quantity == Quantity(2)


def test_unrelated_position_sequence_conflict_is_not_already_applied(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, first_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    opened = service(mssql_database.engine).project_fill(first_fill.fill_id)
    _, _, _, occupying_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    _, _, _, target_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.position_events.add(
            new_event(
                position_id=opened.position_id,
                fill_id=occupying_fill.fill_id,
                sequence=2,
                quantity_delta=1,
                quantity_after=2,
                average="25",
                occurred_at=occupying_fill.executed_at,
            )
        )
        unit_of_work.commit()
    before = get_position(mssql_database.engine, opened.position_id)

    with pytest.raises(PositionProjectionConcurrencyError):
        service(mssql_database.engine).project_fill(target_fill.fill_id)

    assert get_event(mssql_database.engine, target_fill.fill_id) is None
    assert get_position(mssql_database.engine, opened.position_id) == before


def test_different_fill_stale_attempt_has_no_lost_update_and_retry_succeeds(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, first_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    opened = service(mssql_database.engine).project_fill(first_fill.fill_id)
    _, _, _, second_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    _, _, _, third_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    second = service(mssql_database.engine).project_fill(second_fill.fill_id)
    assert second.position_version == 2
    position_v2 = get_position(mssql_database.engine, opened.position_id)
    assert position_v2 is not None
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work, pytest.raises(OptimisticConcurrencyError):
        unit_of_work.position_events.add(
            new_event(
                position_id=opened.position_id,
                fill_id=third_fill.fill_id,
                sequence=3,
                quantity_delta=1,
                quantity_after=3,
                average="25",
                occurred_at=third_fill.executed_at,
            )
        )
        unit_of_work.paper_positions.transition_after_buy_fill(
            PaperPositionBuyTransition(
                position_id=opened.position_id,
                expected_version=1,
                quantity=Quantity(3),
                average_cost_price=Price(Decimal("25")),
                updated_at=third_fill.executed_at,
            )
        )
        unit_of_work.commit()

    assert get_event(mssql_database.engine, third_fill.fill_id) is None
    assert get_position(mssql_database.engine, opened.position_id) == position_v2
    third = service(mssql_database.engine).project_fill(third_fill.fill_id)
    final_position = get_position(mssql_database.engine, opened.position_id)
    assert third.position_version == 3
    assert third.quantity == Quantity(3)
    assert final_position is not None and final_position.version == 3
