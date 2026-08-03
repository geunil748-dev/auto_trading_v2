"""Real MSSQL TradeIntent-to-PaperOrder submission behavior."""

from dataclasses import replace

import pytest

from auto_trading_v2.adapters.brokers import InternalPaperBroker
from auto_trading_v2.adapters.identifiers import Uuid5ClientOrderIDFactory
from auto_trading_v2.application.errors import PaperOrderConflictError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.trade_intents import TradeSide
from tests.integration.paper_orders.helpers import downstream_counts, service
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.trade_intents.helpers import (
    decisions_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
)
from tests.integration.trade_intents.helpers import (
    service as trade_intent_service,
)

pytestmark = pytest.mark.integration


class CountingInternalPaperBroker(InternalPaperBroker):
    def __init__(self) -> None:
        self.calls = 0

    def submit(self, request):
        self.calls += 1
        return super().submit(request)


def candidate(database: TemporaryMssqlDatabase):
    return prepare_decided_candidate(
        database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )


def test_pr7_trade_intent_is_accepted_without_downstream_projection(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = candidate(mssql_database)
    intent = trade_intent_service(mssql_database.engine).create_all(candidate_id).trade_intents[0]
    source_before = intent
    before = downstream_counts(mssql_database.engine)

    stored = service(mssql_database.engine).submit(intent.trade_intent_id)

    after = downstream_counts(mssql_database.engine)
    assert stored.trade_intent_id == intent.trade_intent_id
    assert stored.client_order_id == Uuid5ClientOrderIDFactory().for_trade_intent(
        intent.trade_intent_id
    )
    assert stored.broker_code == "INTERNAL_PAPER"
    assert stored.broker_order_ref == f"internal-paper:v1:{stored.client_order_id}"
    assert stored.status is PaperOrderStatus.ACCEPTED
    assert stored.submitted_at == stored.accepted_at == stored.updated_at
    assert stored.closed_at is None and stored.rejection_code is None
    assert stored.version == 1 and stored.recorded_at.tzinfo is not None
    assert after == (before[0] + 1, before[1], before[2])
    with pytest.raises(PaperOrderConflictError):
        service(mssql_database.engine).submit(intent.trade_intent_id)
    with pytest.raises(PaperOrderConflictError):
        service(mssql_database.engine).submit(intent.trade_intent_id)
    assert intent == source_before
    assert downstream_counts(mssql_database.engine) == after


def test_valid_sell_intent_is_stored_as_rejected_not_application_failure(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = candidate(mssql_database)
    decision = decisions_for(mssql_database.engine, candidate_id)[0]
    sell_intent = persist_intent(
        mssql_database.engine,
        replace(new_intent(decision), side=TradeSide.SELL),
    )
    before = downstream_counts(mssql_database.engine)

    stored = service(mssql_database.engine).submit(sell_intent.trade_intent_id)

    after = downstream_counts(mssql_database.engine)
    assert stored.status is PaperOrderStatus.REJECTED
    assert stored.rejection_code == "UNSUPPORTED_SIDE"
    assert stored.broker_order_ref == f"internal-paper:v1:{stored.client_order_id}"
    assert stored.accepted_at is None
    assert stored.closed_at == stored.submitted_at == stored.updated_at
    assert after == (before[0] + 1, before[1], before[2])


def test_reexecution_precheck_does_not_call_broker_again(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = candidate(mssql_database)
    intent = trade_intent_service(mssql_database.engine).create_all(candidate_id).trade_intents[0]
    broker = CountingInternalPaperBroker()
    submission_service = service(mssql_database.engine, broker)
    original = submission_service.submit(intent.trade_intent_id)

    with pytest.raises(PaperOrderConflictError):
        submission_service.submit(intent.trade_intent_id)

    assert broker.calls == 1
    assert original.status is PaperOrderStatus.ACCEPTED
