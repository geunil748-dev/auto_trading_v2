"""Real MSSQL Position repositories, constraints, and transaction ownership."""

from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    ForeignKeyViolationError,
)
from auto_trading_v2.domain.primitives import FillID, PositionID, StrategyID
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.position_projection.helpers import (
    get_event,
    get_position,
    prepare_fill,
)
from tests.integration.position_projection.test_position_projection_atomicity import (
    new_event,
    new_position,
)

pytestmark = pytest.mark.integration


def test_position_and_event_round_trip_all_projection_lookups(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, intent, _, fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    position_id = PositionID(uuid4())
    position = new_position(
        position_id=position_id,
        strategy_id=strategy_id,
        occurred_at=fill.executed_at,
    )
    event = new_event(
        position_id=position_id,
        fill_id=fill.fill_id,
        sequence=1,
        quantity_delta=1,
        quantity_after=1,
        average=str(fill.price.value),
        occurred_at=fill.executed_at,
    )
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        stored_position = unit_of_work.paper_positions.add(position)
        stored_event = unit_of_work.position_events.add(event)
        unit_of_work.commit()
    with factory() as unit_of_work:
        assert unit_of_work.paper_positions.get(position_id) == stored_position
        assert (
            unit_of_work.paper_positions.get_open_by_key(
                strategy_id=strategy_id,
                symbol=intent.symbol,
                currency=intent.currency,
            )
            == stored_position
        )
        assert unit_of_work.position_events.get(stored_event.position_event_id) == stored_event
        assert unit_of_work.position_events.get_by_fill_id(fill.fill_id) == stored_event

    assert stored_position.recorded_at.tzinfo is not None
    assert stored_event.recorded_at.tzinfo is not None


def test_repositories_do_not_commit_implicitly(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    position_id = PositionID(uuid4())

    with SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work:
        unit_of_work.paper_positions.add(
            new_position(
                position_id=position_id,
                strategy_id=strategy_id,
                occurred_at=fill.executed_at,
            )
        )

    assert get_position(mssql_database.engine, position_id) is None


def test_open_key_and_event_uniques_are_final_race_defenses(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, first_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    _, _, _, second_fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    position_id = PositionID(uuid4())
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.paper_positions.add(
            new_position(
                position_id=position_id,
                strategy_id=strategy_id,
                occurred_at=first_fill.executed_at,
            )
        )
        unit_of_work.position_events.add(
            new_event(
                position_id=position_id,
                fill_id=first_fill.fill_id,
                sequence=1,
                quantity_delta=1,
                quantity_after=1,
                average="25",
                occurred_at=first_fill.executed_at,
            )
        )
        unit_of_work.commit()

    duplicate_open = new_position(
        position_id=PositionID(uuid4()),
        strategy_id=strategy_id,
        occurred_at=first_fill.executed_at,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError) as captured:
        unit_of_work.paper_positions.add(duplicate_open)
    assert captured.value.constraint == "ix_paper_positions_open_unique"

    duplicate_fill = new_event(
        position_id=position_id,
        fill_id=first_fill.fill_id,
        sequence=2,
        quantity_delta=1,
        quantity_after=2,
        average="25",
        occurred_at=first_fill.executed_at,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError) as captured:
        unit_of_work.position_events.add(duplicate_fill)
    assert captured.value.constraint == "uq_position_events_fill_id"

    duplicate_sequence = new_event(
        position_id=position_id,
        fill_id=second_fill.fill_id,
        sequence=1,
        quantity_delta=1,
        quantity_after=1,
        average="25",
        occurred_at=second_fill.executed_at,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError) as captured:
        unit_of_work.position_events.add(duplicate_sequence)
    assert captured.value.constraint == "uq_position_events_position_sequence"
    assert get_event(mssql_database.engine, second_fill.fill_id) is None


def test_position_event_foreign_keys_translate_safely(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    strategy_id = StrategyID(uuid4())
    _, _, _, fill = prepare_fill(mssql_database.engine, strategy_id=strategy_id)
    position_id = PositionID(uuid4())
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.paper_positions.add(
            new_position(
                position_id=position_id,
                strategy_id=strategy_id,
                occurred_at=fill.executed_at,
            )
        )
        unit_of_work.commit()

    missing_position = new_event(
        position_id=PositionID(uuid4()),
        fill_id=fill.fill_id,
        sequence=1,
        quantity_delta=1,
        quantity_after=1,
        average="25",
        occurred_at=fill.executed_at,
    )
    with factory() as unit_of_work, pytest.raises(ForeignKeyViolationError) as captured:
        unit_of_work.position_events.add(missing_position)
    assert captured.value.constraint == "fk_position_events_position_id_paper_positions"

    missing_fill = new_event(
        position_id=position_id,
        fill_id=FillID(uuid4()),
        sequence=1,
        quantity_delta=1,
        quantity_after=1,
        average="25",
        occurred_at=fill.executed_at,
    )
    with factory() as unit_of_work, pytest.raises(ForeignKeyViolationError) as captured:
        unit_of_work.position_events.add(missing_fill)
    assert captured.value.constraint == "fk_position_events_fill_id_paper_fills"
