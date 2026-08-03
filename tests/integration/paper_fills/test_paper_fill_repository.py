"""Real MSSQL round-trip, ordering, uniqueness, and FK coverage."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import paper_orders
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_fills import NewPaperFill
from auto_trading_v2.application.errors import DuplicateRecordError, ForeignKeyViolationError
from auto_trading_v2.domain.paper_fills import paper_fill_execution_key
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    OrderID,
    Price,
    Quantity,
)
from tests.integration.paper_fills.helpers import EXECUTED_AT, fills_for, prepare_order
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def new_fill(
    order_id: OrderID,
    sequence: int,
    quantity: int,
    *,
    key: str | None = None,
) -> NewPaperFill:
    return NewPaperFill(
        fill_id=FillID(uuid4()),
        order_id=order_id,
        execution_key=key or paper_fill_execution_key(order_id, sequence),
        fill_sequence=sequence,
        quantity=Quantity(quantity),
        price=Price(Decimal("25.125000000000000000")),
        fee=Money(Decimal("0"), Currency("USD")),
        executed_at=EXECUTED_AT + timedelta(microseconds=sequence),
    )


def test_round_trip_all_lookups_decimal_time_currency_and_ordering(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, order = prepare_order(mssql_database.engine)
    second = new_fill(order.order_id, 2, 20)
    first = new_fill(order.order_id, 1, 20)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        stored_second = unit_of_work.paper_fills.add(second)
        stored_first = unit_of_work.paper_fills.add(first)
        unit_of_work.commit()
    with factory() as unit_of_work:
        assert unit_of_work.paper_fills.get(stored_first.fill_id) == stored_first
        assert unit_of_work.paper_fills.get(FillID(uuid4())) is None
        assert unit_of_work.paper_fills.get_by_execution_key(first.execution_key) == stored_first
        assert (
            unit_of_work.paper_fills.get_by_order_sequence(
                order_id=order.order_id,
                fill_sequence=2,
            )
            == stored_second
        )
        listed = tuple(unit_of_work.paper_fills.list_by_order(order.order_id))

    assert listed == (stored_first, stored_second)
    assert listed[0].quantity == Quantity(20)
    assert listed[0].price.value == Decimal("25.125000000000000000")
    assert listed[0].fee == Money(Decimal("0E-18"), Currency("USD"))
    assert listed[0].executed_at == first.executed_at
    assert listed[0].executed_at.tzinfo is not None
    assert listed[0].recorded_at.tzinfo is not None


def test_repository_does_not_commit_implicitly(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, order = prepare_order(mssql_database.engine)
    value = new_fill(order.order_id, 1, 20)

    with SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work:
        unit_of_work.paper_fills.add(value)

    assert fills_for(mssql_database.engine, order.order_id) == ()


def test_unique_execution_sequence_and_parent_fk_are_final_defenses(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, order = prepare_order(mssql_database.engine)
    original = new_fill(order.order_id, 1, 20)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.paper_fills.add(original)
        unit_of_work.commit()

    duplicate_key = replace(original, fill_id=FillID(uuid4()), fill_sequence=2)
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.paper_fills.add(duplicate_key)

    duplicate_sequence = replace(
        original,
        fill_id=FillID(uuid4()),
        execution_key=f"{original.execution_key}|distinct",
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.paper_fills.add(duplicate_sequence)

    missing_parent = new_fill(OrderID(uuid4()), 1, 1)
    with factory() as unit_of_work, pytest.raises(ForeignKeyViolationError):
        unit_of_work.paper_fills.add(missing_parent)

    stored = fills_for(mssql_database.engine, order.order_id)
    assert len(stored) == 1
    assert stored[0].fill_id == original.fill_id


def test_order_with_fill_cannot_be_deleted_by_cascade(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, order = prepare_order(mssql_database.engine)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.paper_fills.add(new_fill(order.order_id, 1, 20))
        unit_of_work.commit()

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            paper_orders.delete().where(paper_orders.c.order_id == order.order_id.value)
        )

    assert len(fills_for(mssql_database.engine, order.order_id)) == 1
