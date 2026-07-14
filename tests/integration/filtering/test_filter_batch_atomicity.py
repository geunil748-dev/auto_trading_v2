"""Real MSSQL duplicate-in-the-middle rollback behavior."""

import pytest

from auto_trading_v2.application.errors import FilterEvaluationConflictError
from auto_trading_v2.domain.filtering.catalog import BALANCED
from tests.integration.filtering.helpers import (
    evaluations_for,
    persist_balanced_evaluation,
    persist_candidate,
    service,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def test_balanced_duplicate_rolls_back_new_strict_and_stops_later_sets(
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

    with pytest.raises(FilterEvaluationConflictError) as caught:
        service(mssql_database.engine).evaluate_all(candidate_id)

    assert caught.value.filter_set_name is BALANCED.name
    assert "SQL" not in str(caught.value)
    persisted = evaluations_for(mssql_database.engine, candidate_id)
    assert persisted == (existing,)
