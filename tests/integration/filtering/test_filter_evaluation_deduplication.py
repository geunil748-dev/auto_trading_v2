"""Real MSSQL full-batch re-evaluation conflict behavior."""

import pytest

from auto_trading_v2.application.errors import FilterEvaluationConflictError
from auto_trading_v2.domain.filtering.catalog import STRICT
from tests.integration.filtering.helpers import evaluations_for, persist_candidate, service
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def test_full_re_evaluation_is_rejected_without_overwrite_or_delete(
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
    service(mssql_database.engine).evaluate_all(candidate_id)
    before = evaluations_for(mssql_database.engine, candidate_id)

    with pytest.raises(FilterEvaluationConflictError) as caught:
        service(mssql_database.engine).evaluate_all(candidate_id)

    after = evaluations_for(mssql_database.engine, candidate_id)
    assert caught.value.filter_set_name is STRICT.name
    assert len(before) == 4
    assert after == before
