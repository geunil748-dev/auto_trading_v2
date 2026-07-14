"""Real MSSQL replay conflict without overwrite or upsert."""

import pytest

from auto_trading_v2.application.errors import TradeIntentConflictError
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.trade_intents.helpers import (
    intents_for,
    prepare_decided_candidate,
    service,
)

pytestmark = pytest.mark.integration


def test_reexecuting_completed_batch_preserves_existing_three_rows(
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
    trade_intent_service = service(mssql_database.engine)
    first = trade_intent_service.create_all(candidate_id)
    before = intents_for(mssql_database.engine, candidate_id)

    with pytest.raises(TradeIntentConflictError):
        service(mssql_database.engine).create_all(candidate_id)

    after = intents_for(mssql_database.engine, candidate_id)
    assert len(first.trade_intents) == 3
    assert len(after) == 3
    assert after == before
