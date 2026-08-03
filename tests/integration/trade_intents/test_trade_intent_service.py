"""Real MSSQL safe no-write behavior for a missing candidate."""

from uuid import uuid4

import pytest

from auto_trading_v2.application.errors import CandidateNotFoundError
from auto_trading_v2.domain.primitives import CandidateID
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.trade_intents.helpers import service

pytestmark = pytest.mark.integration


def test_missing_candidate_fails_without_trade_intent_write(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = CandidateID(uuid4())

    with pytest.raises(CandidateNotFoundError):
        service(mssql_database.engine).create_all(candidate_id)
