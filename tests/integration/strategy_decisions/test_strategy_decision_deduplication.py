"""Real MSSQL full-batch re-execution and missing-source behavior."""

import pytest

from auto_trading_v2.application.errors import (
    RequiredFilterEvaluationMissingError,
    StrategyDecisionConflictError,
)
from tests.integration.filtering.helpers import (
    evaluations_for,
    persist_balanced_evaluation,
    persist_candidate,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import (
    decisions_for,
    prepare_candidate,
    strategy_service,
)

pytestmark = pytest.mark.integration


def test_full_batch_reexecution_conflicts_without_overwrite_or_new_keys(
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
    service = strategy_service(mssql_database.engine)
    service.decide_all(candidate_id)
    before = decisions_for(mssql_database.engine, candidate_id)

    with pytest.raises(StrategyDecisionConflictError):
        service.decide_all(candidate_id)

    assert decisions_for(mssql_database.engine, candidate_id) == before
    assert len(before) == 4


def test_missing_required_evaluations_write_nothing_and_preserve_existing_source(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = persist_candidate(
        mssql_database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )
    existing = persist_balanced_evaluation(mssql_database.engine, candidate_id)

    with pytest.raises(RequiredFilterEvaluationMissingError):
        strategy_service(mssql_database.engine).decide_all(candidate_id)

    assert decisions_for(mssql_database.engine, candidate_id) == ()
    assert evaluations_for(mssql_database.engine, candidate_id) == (existing,)
