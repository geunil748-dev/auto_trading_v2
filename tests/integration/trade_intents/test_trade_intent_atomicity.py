"""Real MSSQL rollback of a partially inserted TradeIntent batch."""

import pytest

from auto_trading_v2.application.errors import TradeIntentConflictError
from auto_trading_v2.domain.strategy_decisions.catalog import BALANCED_ENTRY
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import candidate_for
from tests.integration.trade_intents.helpers import (
    decisions_for,
    intents_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
    service,
)

pytestmark = pytest.mark.integration


def test_duplicate_second_intent_rolls_back_new_first_intent(
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
    decisions_before = decisions_for(mssql_database.engine, candidate_id)
    evaluations_before = evaluations_for(mssql_database.engine, candidate_id)
    candidate_before = candidate_for(mssql_database.engine, candidate_id)
    balanced = next(
        item for item in decisions_before if item.strategy_id == BALANCED_ENTRY.strategy_id
    )
    existing = persist_intent(mssql_database.engine, new_intent(balanced))

    with pytest.raises(TradeIntentConflictError) as captured:
        service(mssql_database.engine).create_all(candidate_id)

    remaining = intents_for(mssql_database.engine, candidate_id)
    assert captured.value.strategy_name == BALANCED_ENTRY.name
    assert remaining == (existing,)
    assert decisions_for(mssql_database.engine, candidate_id) == decisions_before
    assert evaluations_for(mssql_database.engine, candidate_id) == evaluations_before
    assert candidate_for(mssql_database.engine, candidate_id) == candidate_before
