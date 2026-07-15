"""Case A-D canonical fill counts over the complete existing pipeline."""

from decimal import Decimal

import pytest

from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.paper_fills.helpers import (
    fills_for,
    prepare_case_orders,
    projector_counts,
    service,
    total_fill_quantity,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import candidate_for
from tests.integration.strategy_decisions.test_strategy_decision_cases import CASES, Case
from tests.integration.trade_intents.helpers import decisions_for, intents_for

pytestmark = pytest.mark.integration

EXPECTED = {
    "all-pass": (3, 40, (20, 20), 6),
    "breakout-fails": (2, 41, (20, 21), 4),
    "previous-close-missing": (1, 40, (20, 20), 2),
    "price-range-fails": (1, 3, (1, 2), 2),
}


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.name)
def test_cases_fill_each_accepted_order_to_exact_terminal_state(
    mssql_database: TemporaryMssqlDatabase,
    case: Case,
) -> None:
    expected_orders, expected_quantity, expected_chunks, expected_fill_count = EXPECTED[case.name]
    candidate_id, intents, orders = prepare_case_orders(mssql_database.engine, **case.values)
    candidate_before = candidate_for(mssql_database.engine, candidate_id)
    evaluations_before = evaluations_for(mssql_database.engine, candidate_id)
    decisions_before = decisions_for(mssql_database.engine, candidate_id)
    intents_before = intents_for(mssql_database.engine, candidate_id)
    projectors_before = projector_counts(mssql_database.engine)
    executor = service(mssql_database.engine)

    results = []
    for source_order in orders:
        results.append(executor.execute_next(source_order.order_id))
        results.append(executor.execute_next(source_order.order_id))

    all_fills = tuple(
        fill
        for source_order in orders
        for fill in fills_for(mssql_database.engine, source_order.order_id)
    )
    assert len(orders) == len(intents) == expected_orders
    assert len(results) == expected_fill_count
    assert len(all_fills) == expected_fill_count
    assert len({item.execution_key for item in all_fills}) == expected_fill_count
    assert all(item.price.value == Decimal(str(case.values["last_price"])) for item in all_fills)
    for source_order, source_intent in zip(orders, intents, strict=True):
        stored = fills_for(mssql_database.engine, source_order.order_id)
        assert tuple(item.fill_sequence for item in stored) == (1, 2)
        assert tuple(item.quantity.value for item in stored) == expected_chunks
        assert total_fill_quantity(stored) == expected_quantity
        assert total_fill_quantity(stored) == source_intent.requested_quantity.value
        assert all(item.fee.amount == 0 for item in stored)
        assert all(item.fee.currency == source_intent.currency for item in stored)
        assert results.pop(0).paper_order.status is PaperOrderStatus.PARTIALLY_FILLED
        assert results.pop(0).paper_order.status is PaperOrderStatus.FILLED

    assert candidate_for(mssql_database.engine, candidate_id) == candidate_before
    assert evaluations_for(mssql_database.engine, candidate_id) == evaluations_before
    assert decisions_for(mssql_database.engine, candidate_id) == decisions_before
    assert intents_for(mssql_database.engine, candidate_id) == intents_before
    assert projector_counts(mssql_database.engine) == projectors_before
