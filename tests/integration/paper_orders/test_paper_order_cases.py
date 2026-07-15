"""Case A-D PaperOrder counts over the existing canonical pipeline."""

import pytest

from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.paper_orders.helpers import downstream_counts, service
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import candidate_for
from tests.integration.strategy_decisions.test_strategy_decision_cases import CASES, Case
from tests.integration.trade_intents.helpers import (
    decisions_for,
    intents_for,
    prepare_decided_candidate,
)
from tests.integration.trade_intents.helpers import (
    service as trade_intent_service,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_cases_submit_only_enter_long_intents_as_one_accepted_order_each(
    mssql_database: TemporaryMssqlDatabase,
    case: Case,
) -> None:
    candidate_id = prepare_decided_candidate(mssql_database.engine, **case.values)
    candidate_before = candidate_for(mssql_database.engine, candidate_id)
    evaluations_before = evaluations_for(mssql_database.engine, candidate_id)
    decisions_before = decisions_for(mssql_database.engine, candidate_id)
    before = downstream_counts(mssql_database.engine)
    intents = trade_intent_service(mssql_database.engine).create_all(candidate_id).trade_intents

    orders = tuple(
        service(mssql_database.engine).submit(intent.trade_intent_id) for intent in intents
    )

    expected = sum(decision.action is StrategyAction.ENTER_LONG for decision in decisions_before)
    assert expected in {1, 2, 3}
    assert len(intents) == len(orders) == expected
    assert all(order.status is PaperOrderStatus.ACCEPTED for order in orders)
    assert {order.trade_intent_id for order in orders} == {
        intent.trade_intent_id for intent in intents
    }
    assert len({order.client_order_id for order in orders}) == expected
    assert len({order.broker_order_ref for order in orders}) == expected
    persisted_intents = intents_for(mssql_database.engine, candidate_id)
    assert {item.trade_intent_id: item for item in persisted_intents} == {
        item.trade_intent_id: item for item in intents
    }
    assert candidate_for(mssql_database.engine, candidate_id) == candidate_before
    assert evaluations_for(mssql_database.engine, candidate_id) == evaluations_before
    assert decisions_for(mssql_database.engine, candidate_id) == decisions_before
    after = downstream_counts(mssql_database.engine)
    assert after == (before[0] + expected, before[1], before[2])
