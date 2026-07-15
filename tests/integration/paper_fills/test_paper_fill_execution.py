"""End-to-end deterministic first, final, single, and rejected fill behavior."""

from dataclasses import replace

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import PaperOrderNotFillableError
from auto_trading_v2.domain.paper_fills import paper_fill_execution_key
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import Quantity
from auto_trading_v2.domain.trade_intents import TradeSide
from tests.integration.paper_fills.helpers import (
    average_price_not_stored,
    fills_for,
    get_order,
    prepare_order,
    projector_counts,
    service,
    total_fill_quantity,
)
from tests.integration.paper_orders.helpers import service as paper_order_service
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.trade_intents.helpers import (
    decisions_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
)

pytestmark = pytest.mark.integration


def test_first_partial_then_final_fill_is_exact_and_projector_free(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    intent, original_order = prepare_order(mssql_database.engine, quantity=41)
    before_projectors = projector_counts(mssql_database.engine)
    executor = service(mssql_database.engine)

    first = executor.execute_next(original_order.order_id)
    first_fills = fills_for(mssql_database.engine, original_order.order_id)

    assert len(first_fills) == 1
    assert first.paper_fill == first_fills[0]
    assert first.paper_fill.fill_sequence == 1
    assert first.paper_fill.quantity == Quantity(20)
    assert first.paper_fill.price.value == 25
    assert first.paper_fill.fee.amount == 0
    assert first.paper_fill.fee.currency == intent.currency
    assert first.paper_order.status is PaperOrderStatus.PARTIALLY_FILLED
    assert first.paper_order.version == 2
    assert first.paper_order.closed_at is None
    assert total_fill_quantity(first_fills) < intent.requested_quantity.value

    second = executor.execute_next(original_order.order_id)
    all_fills = fills_for(mssql_database.engine, original_order.order_id)

    assert len(all_fills) == 2
    assert tuple(item.fill_sequence for item in all_fills) == (1, 2)
    assert tuple(item.quantity.value for item in all_fills) == (20, 21)
    assert second.paper_fill.execution_key == paper_fill_execution_key(original_order.order_id, 2)
    assert second.paper_order.status is PaperOrderStatus.FILLED
    assert second.paper_order.version == 3
    assert second.paper_order.closed_at == second.paper_fill.executed_at
    assert total_fill_quantity(all_fills) == intent.requested_quantity.value
    assert average_price_not_stored()
    assert projector_counts(mssql_database.engine) == before_projectors


def test_quantity_one_fills_directly_without_partial_state(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    intent, original_order = prepare_order(mssql_database.engine, quantity=1)

    result = service(mssql_database.engine).execute_next(original_order.order_id)

    stored = fills_for(mssql_database.engine, original_order.order_id)
    assert len(stored) == 1
    assert stored[0].quantity == Quantity(1)
    assert total_fill_quantity(stored) == intent.requested_quantity.value
    assert result.paper_order.status is PaperOrderStatus.FILLED
    assert result.paper_order.version == 2
    assert result.paper_order.closed_at == result.paper_fill.executed_at


def test_rejected_order_and_filled_reexecution_write_no_fill(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = prepare_decided_candidate(
        mssql_database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )
    sell_intent = persist_intent(
        mssql_database.engine,
        replace(
            new_intent(decisions_for(mssql_database.engine, candidate_id)[0]), side=TradeSide.SELL
        ),
    )
    rejected = paper_order_service(mssql_database.engine).submit(sell_intent.trade_intent_id)
    assert rejected.status is PaperOrderStatus.REJECTED

    executor = service(mssql_database.engine)
    with pytest.raises(PaperOrderNotFillableError):
        executor.execute_next(rejected.order_id)
    assert fills_for(mssql_database.engine, rejected.order_id) == ()
    assert get_order(mssql_database.engine, rejected.order_id) == rejected

    _, accepted = prepare_order(mssql_database.engine, quantity=1)
    executor.execute_next(accepted.order_id)
    before_fills = fills_for(mssql_database.engine, accepted.order_id)
    before_order = get_order(mssql_database.engine, accepted.order_id)
    with pytest.raises(PaperOrderNotFillableError):
        executor.execute_next(accepted.order_id)
    assert fills_for(mssql_database.engine, accepted.order_id) == before_fills
    assert get_order(mssql_database.engine, accepted.order_id) == before_order
    assert len(before_fills) == 1


def test_upstream_intent_is_unchanged_by_fill_execution(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    intent, original_order = prepare_order(mssql_database.engine)

    service(mssql_database.engine).execute_next(original_order.order_id)

    with SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work:
        assert unit_of_work.trade_intents.get(intent.trade_intent_id) == intent
