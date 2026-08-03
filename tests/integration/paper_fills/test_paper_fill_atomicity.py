"""Real MSSQL duplicate and stale-transition rollback guarantees."""

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_fills import PaperOrderFillTransition
from auto_trading_v2.application.errors import DuplicateRecordError, OptimisticConcurrencyError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from tests.integration.paper_fills.helpers import (
    EXECUTED_AT,
    fills_for,
    get_order,
    prepare_order,
)
from tests.integration.paper_fills.test_paper_fill_repository import new_fill
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def partial_transition(order_id, expected_version: int = 1) -> PaperOrderFillTransition:
    return PaperOrderFillTransition(
        order_id=order_id,
        expected_status=PaperOrderStatus.ACCEPTED,
        expected_version=expected_version,
        new_status=PaperOrderStatus.PARTIALLY_FILLED,
        closed_at=None,
        updated_at=EXECUTED_AT,
    )


def test_duplicate_fill_rolls_back_without_order_transition(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, original_order = prepare_order(mssql_database.engine)
    original_fill = new_fill(original_order.order_id, 1, 20)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        stored = unit_of_work.paper_fills.add(original_fill)
        unit_of_work.commit()

    before_order = get_order(mssql_database.engine, original_order.order_id)
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.paper_fills.add(original_fill)
        unit_of_work.paper_orders.transition_after_fill(partial_transition(original_order.order_id))
        unit_of_work.commit()

    assert fills_for(mssql_database.engine, original_order.order_id) == (stored,)
    assert get_order(mssql_database.engine, original_order.order_id) == before_order


def test_stale_transition_rolls_back_fill_insert_and_preserves_committed_version_two(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, original_order = prepare_order(mssql_database.engine)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        version_two = unit_of_work.paper_orders.transition_after_fill(
            partial_transition(original_order.order_id)
        )
        unit_of_work.commit()
    assert version_two.status is PaperOrderStatus.PARTIALLY_FILLED
    assert version_two.version == 2
    assert fills_for(mssql_database.engine, original_order.order_id) == ()

    planned_fill = new_fill(original_order.order_id, 1, 20)
    with factory() as unit_of_work, pytest.raises(OptimisticConcurrencyError):
        unit_of_work.paper_fills.add(planned_fill)
        unit_of_work.paper_orders.transition_after_fill(
            partial_transition(original_order.order_id, expected_version=1)
        )
        unit_of_work.commit()

    assert fills_for(mssql_database.engine, original_order.order_id) == ()
    assert get_order(mssql_database.engine, original_order.order_id) == version_two
