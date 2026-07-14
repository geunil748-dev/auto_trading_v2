"""Real MSSQL TradeIntent repository round-trip and transaction behavior."""

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import DuplicateRecordError, ForeignKeyViolationError
from auto_trading_v2.domain.primitives import DecisionID, TradeIntentID
from auto_trading_v2.domain.strategy_decisions.catalog import BALANCED_ENTRY, STRICT_ENTRY
from auto_trading_v2.domain.trade_intents import TradeOrderType
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.trade_intents.helpers import (
    decisions_for,
    new_intent,
    persist_intent,
    prepare_decided_candidate,
)

pytestmark = pytest.mark.integration


def _candidate(database: TemporaryMssqlDatabase):
    candidate_id = prepare_decided_candidate(
        database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )
    return candidate_id


def test_repository_add_get_lookup_market_and_limit_round_trip(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = _candidate(mssql_database)
    decisions = decisions_for(mssql_database.engine, candidate_id)
    strict = next(item for item in decisions if item.strategy_id == STRICT_ENTRY.strategy_id)
    balanced = next(item for item in decisions if item.strategy_id == BALANCED_ENTRY.strategy_id)
    market = new_intent(strict)
    limit = new_intent(
        balanced,
        order_type=TradeOrderType.LIMIT,
        limit_price=Decimal("25.123456789012345678"),
    )
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        stored_market = unit_of_work.trade_intents.add(market)
        stored_limit = unit_of_work.trade_intents.add(limit)
        unit_of_work.commit()
    with factory() as unit_of_work:
        assert unit_of_work.trade_intents.get(stored_market.trade_intent_id) == stored_market
        assert unit_of_work.trade_intents.get(TradeIntentID(uuid4())) is None
        assert unit_of_work.trade_intents.get_by_decision(strict.decision_id) == stored_market
        assert (
            unit_of_work.trade_intents.get_by_idempotency_key(market.idempotency_key)
            == stored_market
        )
        assert unit_of_work.trade_intents.get(stored_limit.trade_intent_id) == stored_limit

    assert stored_market.limit_price is None
    assert stored_market.recorded_at.tzinfo is not None
    assert stored_market.requested_quantity.value == 40
    assert stored_limit.limit_price is not None
    assert stored_limit.limit_price.value == Decimal("25.123456789012345678")


def test_repository_does_not_commit_implicitly(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = _candidate(mssql_database)
    decision = decisions_for(mssql_database.engine, candidate_id)[0]
    intent = new_intent(decision)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        unit_of_work.trade_intents.add(intent)
    with factory() as unit_of_work:
        assert unit_of_work.trade_intents.get(intent.trade_intent_id) is None


def test_repository_translates_foreign_key_and_both_unique_constraints(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    first_candidate = _candidate(mssql_database)
    first = decisions_for(mssql_database.engine, first_candidate)[0]
    original = persist_intent(mssql_database.engine, new_intent(first))
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    missing_parent = replace(
        new_intent(first),
        trade_intent_id=TradeIntentID(uuid4()),
        decision_id=DecisionID(uuid4()),
        idempotency_key="missing-parent",
    )
    with factory() as unit_of_work, pytest.raises(ForeignKeyViolationError):
        unit_of_work.trade_intents.add(missing_parent)

    duplicate_decision = replace(
        new_intent(first),
        trade_intent_id=TradeIntentID(uuid4()),
        idempotency_key="different-key",
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.trade_intents.add(duplicate_decision)

    second_candidate = _candidate(mssql_database)
    second = decisions_for(mssql_database.engine, second_candidate)[0]
    duplicate_key = replace(
        new_intent(second),
        idempotency_key=original.idempotency_key,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.trade_intents.add(duplicate_key)
