"""End-to-end TradeIntent counts and quantities for PR5/PR6 cases A-D."""

from decimal import ROUND_FLOOR, Decimal, localcontext

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import candidate_for
from tests.integration.strategy_decisions.test_strategy_decision_cases import CASES, Case
from tests.integration.trade_intents.helpers import (
    CREATED_AT,
    decisions_for,
    downstream_counts,
    intents_for,
    prepare_decided_candidate,
    service,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_cases_create_only_enter_long_intents_with_exact_quantity(
    mssql_database: TemporaryMssqlDatabase,
    case: Case,
) -> None:
    candidate_id = prepare_decided_candidate(mssql_database.engine, **case.values)
    candidate_before = candidate_for(mssql_database.engine, candidate_id)
    evaluations_before = evaluations_for(mssql_database.engine, candidate_id)
    decisions_before = decisions_for(mssql_database.engine, candidate_id)
    downstream_before = downstream_counts(mssql_database.engine)
    with SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work:
        snapshot = unit_of_work.market_snapshots.get(candidate_before.market_snapshot_id)
    assert snapshot is not None

    result = service(mssql_database.engine).create_all(candidate_id)

    eligible_decisions = tuple(
        decision for decision in decisions_before if decision.action is StrategyAction.ENTER_LONG
    )
    persisted = intents_for(mssql_database.engine, candidate_id)
    with localcontext() as context:
        context.prec = 38
        expected_quantity = int(
            (Decimal("1000") / snapshot.last_price.value).to_integral_value(rounding=ROUND_FLOOR)
        )
    assert len(result.trade_intents) == len(eligible_decisions)
    assert len(persisted) == len(eligible_decisions)
    assert {item.decision_id for item in persisted} == {
        item.decision_id for item in eligible_decisions
    }
    assert all(item.requested_quantity.value == expected_quantity for item in persisted)
    assert all(item.requested_quantity.value > 0 for item in persisted)
    assert all(
        snapshot.last_price.value * Decimal(item.requested_quantity.value) <= Decimal("1000")
        for item in persisted
    )
    assert all(item.side is TradeSide.BUY for item in persisted)
    assert all(item.order_type is TradeOrderType.MARKET for item in persisted)
    assert all(item.time_in_force is TimeInForce.DAY for item in persisted)
    assert all(item.currency.code == "USD" and item.limit_price is None for item in persisted)
    assert all(
        item.symbol == snapshot.symbol and item.created_at == CREATED_AT for item in persisted
    )
    assert len({item.idempotency_key for item in persisted}) == len(persisted)
    assert candidate_for(mssql_database.engine, candidate_id) == candidate_before
    assert evaluations_for(mssql_database.engine, candidate_id) == evaluations_before
    assert decisions_for(mssql_database.engine, candidate_id) == decisions_before
    assert downstream_counts(mssql_database.engine) == downstream_before
