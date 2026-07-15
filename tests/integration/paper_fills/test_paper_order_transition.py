"""Real MSSQL optimistic fill-only PaperOrder transitions."""

from datetime import timedelta

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.paper_fills import PaperOrderFillTransition
from auto_trading_v2.application.errors import OptimisticConcurrencyError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from tests.integration.paper_fills.helpers import EXECUTED_AT, get_order, prepare_order
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def transition(
    order_id,
    expected_status: PaperOrderStatus,
    expected_version: int,
    new_status: PaperOrderStatus,
    *,
    final: bool = False,
) -> PaperOrderFillTransition:
    updated_at = EXECUTED_AT + timedelta(seconds=expected_version)
    return PaperOrderFillTransition(
        order_id=order_id,
        expected_status=expected_status,
        expected_version=expected_version,
        new_status=new_status,
        closed_at=updated_at if final else None,
        updated_at=updated_at,
    )


def test_partial_then_full_transition_preserves_identity_and_timestamps(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    _, original = prepare_order(mssql_database.engine)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        partial = unit_of_work.paper_orders.transition_after_fill(
            transition(
                original.order_id,
                PaperOrderStatus.ACCEPTED,
                1,
                PaperOrderStatus.PARTIALLY_FILLED,
            )
        )
        unit_of_work.commit()

    assert partial.status is PaperOrderStatus.PARTIALLY_FILLED
    assert partial.version == 2
    assert partial.closed_at is None
    assert partial.accepted_at == original.accepted_at
    assert partial.submitted_at == original.submitted_at
    assert partial.broker_code == original.broker_code
    assert partial.broker_order_ref == original.broker_order_ref
    assert partial.rejection_code == original.rejection_code

    with factory() as unit_of_work:
        filled = unit_of_work.paper_orders.transition_after_fill(
            transition(
                original.order_id,
                PaperOrderStatus.PARTIALLY_FILLED,
                2,
                PaperOrderStatus.FILLED,
                final=True,
            )
        )
        unit_of_work.commit()

    assert filled.status is PaperOrderStatus.FILLED
    assert filled.version == 3
    assert filled.closed_at == filled.updated_at
    assert filled.accepted_at == original.accepted_at


@pytest.mark.parametrize(
    ("expected_status", "expected_version"),
    [(PaperOrderStatus.ACCEPTED, 1), (PaperOrderStatus.ACCEPTED, 2)],
)
def test_stale_version_or_wrong_status_changes_no_row(
    mssql_database: TemporaryMssqlDatabase,
    expected_status: PaperOrderStatus,
    expected_version: int,
) -> None:
    _, original = prepare_order(mssql_database.engine)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        current = unit_of_work.paper_orders.transition_after_fill(
            transition(
                original.order_id,
                PaperOrderStatus.ACCEPTED,
                1,
                PaperOrderStatus.PARTIALLY_FILLED,
            )
        )
        unit_of_work.commit()

    before = get_order(mssql_database.engine, original.order_id)
    with factory() as unit_of_work, pytest.raises(OptimisticConcurrencyError):
        unit_of_work.paper_orders.transition_after_fill(
            transition(
                original.order_id,
                expected_status,
                expected_version,
                PaperOrderStatus.FILLED,
                final=True,
            )
        )

    assert before == current
    assert get_order(mssql_database.engine, original.order_id) == before
