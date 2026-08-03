"""Real MSSQL rollback behavior for a duplicate in the middle of a batch."""

import pytest

from auto_trading_v2.application.errors import StrategyDecisionConflictError
from auto_trading_v2.domain.strategy_decisions.catalog import BALANCED_ENTRY
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import (
    candidate_for,
    decisions_for,
    evaluation_for,
    new_decision,
    persist_single_decision,
    prepare_candidate,
    strategy_service,
)

pytestmark = pytest.mark.integration


def test_duplicate_second_strategy_rolls_back_new_first_strategy(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = prepare_candidate(
        mssql_database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )
    evaluations_before = evaluations_for(mssql_database.engine, candidate_id)
    candidate_before = candidate_for(mssql_database.engine, candidate_id)
    balanced = new_decision(
        candidate_id,
        evaluation_for(mssql_database.engine, candidate_id, BALANCED_ENTRY),
        BALANCED_ENTRY,
    )
    existing = persist_single_decision(mssql_database.engine, balanced)

    with pytest.raises(StrategyDecisionConflictError) as captured:
        strategy_service(mssql_database.engine).decide_all(candidate_id)

    remaining = decisions_for(mssql_database.engine, candidate_id)
    assert captured.value.strategy_name == BALANCED_ENTRY.name
    assert remaining == (existing,)
    assert evaluations_for(mssql_database.engine, candidate_id) == evaluations_before
    assert candidate_for(mssql_database.engine, candidate_id) == candidate_before
