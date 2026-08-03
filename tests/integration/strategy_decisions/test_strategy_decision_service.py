"""Real MSSQL canonical strategy-decision batch verification."""

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    filter_evaluations,
    strategy_decisions,
)
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.decision_keys import (
    candidate_strategy_decision_key,
)
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import (
    DECIDED_AT,
    candidate_for,
    prepare_candidate,
    strategy_service,
)

pytestmark = pytest.mark.integration


def test_normal_batch_persists_only_four_linked_candidate_decisions(
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

    batch = strategy_service(mssql_database.engine).decide_all(candidate_id)

    assert len(batch.decisions) == 4
    assert all(item.candidate_id == candidate_id for item in batch.decisions)
    expected_evaluation_ids = tuple(
        next(
            evaluation.filter_evaluation_id
            for evaluation in evaluations_before
            if evaluation.filter_set_id == definition.source_filter_set_id
            and evaluation.evaluation_version == definition.source_evaluation_version
        )
        for definition in BUILT_IN_STRATEGIES
    )
    assert tuple(item.filter_evaluation_id for item in batch.decisions) == tuple(
        expected_evaluation_ids
    )
    assert tuple(item.strategy_id for item in batch.decisions) == tuple(
        item.strategy_id for item in BUILT_IN_STRATEGIES
    )
    assert all(item.strategy_version == "v1" for item in batch.decisions)
    assert all(item.decided_at == DECIDED_AT for item in batch.decisions)
    assert all(item.recorded_at.tzinfo is not None for item in batch.decisions)
    assert tuple(item.decision_key for item in batch.decisions) == tuple(
        candidate_strategy_decision_key(
            candidate_id,
            definition.strategy_id,
            definition.strategy_version,
        )
        for definition in BUILT_IN_STRATEGIES
    )
    assert evaluations_for(mssql_database.engine, candidate_id) == evaluations_before
    assert candidate_for(mssql_database.engine, candidate_id) == candidate_before

    with mssql_database.engine.connect() as connection:
        rows = connection.execute(
            select(
                strategy_decisions.c.position_id,
                strategy_decisions.c.reason_codes,
            ).where(strategy_decisions.c.candidate_id == candidate_id.value)
        ).all()
        assert len(rows) == 4
        assert all(row.position_id is None for row in rows)
        assert all(str(row.reason_codes).startswith("[") for row in rows)
        assert (
            connection.scalar(
                select(func.count())
                .select_from(candidates)
                .where(candidates.c.candidate_id == candidate_id.value)
            )
            == 1
        )
        assert (
            connection.scalar(
                select(func.count())
                .select_from(filter_evaluations)
                .where(filter_evaluations.c.candidate_id == candidate_id.value)
            )
            == 4
        )
