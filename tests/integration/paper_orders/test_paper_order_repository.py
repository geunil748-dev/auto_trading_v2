"""Real MSSQL PaperOrder repository round-trip and constraints."""

from dataclasses import replace
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import DuplicateRecordError, ForeignKeyViolationError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import ClientOrderID, OrderID, TradeIntentID
from tests.integration.paper_orders.helpers import get_order, new_order
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.trade_intents.helpers import (
    decisions_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
)

pytestmark = pytest.mark.integration


def intent(database: TemporaryMssqlDatabase):
    candidate_id = prepare_decided_candidate(
        database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )
    decision = decisions_for(database.engine, candidate_id)[0]
    return persist_intent(database.engine, new_intent(decision))


def test_accepted_and_rejected_round_trip_all_lookup_paths(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    accepted = new_order(intent(mssql_database))
    rejected = new_order(intent(mssql_database), status=PaperOrderStatus.REJECTED)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        stored_accepted = unit_of_work.paper_orders.add(accepted)
        stored_rejected = unit_of_work.paper_orders.add(rejected)
        unit_of_work.commit()
    with factory() as unit_of_work:
        assert unit_of_work.paper_orders.get(stored_accepted.order_id) == stored_accepted
        assert unit_of_work.paper_orders.get(OrderID(uuid4())) is None
        assert (
            unit_of_work.paper_orders.get_by_trade_intent(accepted.trade_intent_id)
            == stored_accepted
        )
        assert (
            unit_of_work.paper_orders.get_by_client_order_id(accepted.client_order_id)
            == stored_accepted
        )
        assert accepted.broker_order_ref is not None
        assert (
            unit_of_work.paper_orders.get_by_broker_reference(
                broker_code=accepted.broker_code,
                broker_order_ref=accepted.broker_order_ref,
            )
            == stored_accepted
        )

    assert stored_accepted.status is PaperOrderStatus.ACCEPTED
    assert stored_accepted.accepted_at == accepted.accepted_at
    assert stored_accepted.closed_at is None
    assert stored_accepted.rejection_code is None
    assert stored_accepted.version == 1
    assert stored_accepted.recorded_at.tzinfo is not None
    assert stored_rejected.status is PaperOrderStatus.REJECTED
    assert stored_rejected.accepted_at is None
    assert stored_rejected.closed_at == rejected.closed_at
    assert stored_rejected.rejection_code == "UNSUPPORTED_SIDE"


def test_repository_does_not_commit_implicitly(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    value = new_order(intent(mssql_database))
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        unit_of_work.paper_orders.add(value)

    assert get_order(mssql_database.engine, value.order_id) is None


def test_repository_translates_fk_and_all_three_unique_identities(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    first_intent = intent(mssql_database)
    original = new_order(first_intent)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.paper_orders.add(original)
        unit_of_work.commit()

    missing_parent = replace(
        new_order(first_intent),
        order_id=OrderID(uuid4()),
        trade_intent_id=TradeIntentID(uuid4()),
    )
    with factory() as unit_of_work, pytest.raises(ForeignKeyViolationError):
        unit_of_work.paper_orders.add(missing_parent)

    duplicate_intent = replace(
        new_order(first_intent),
        order_id=OrderID(uuid4()),
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.paper_orders.add(duplicate_intent)

    second_intent = intent(mssql_database)
    duplicate_client = new_order(
        second_intent,
        client_order_id=original.client_order_id,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.paper_orders.add(duplicate_client)

    third_intent = intent(mssql_database)
    assert original.broker_order_ref is not None
    duplicate_reference = new_order(
        third_intent,
        client_order_id=ClientOrderID(uuid4()),
        broker_order_ref=original.broker_order_ref,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.paper_orders.add(duplicate_reference)

    assert get_order(mssql_database.engine, original.order_id) is not None
    assert get_order(mssql_database.engine, duplicate_intent.order_id) is None
