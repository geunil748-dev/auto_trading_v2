from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    equity_snapshots,
    filter_evaluations,
    market_snapshots,
    paper_fills,
    paper_orders,
    position_events,
    strategy_decisions,
    trade_intents,
    trading_events,
)

from .helpers import (
    clone_row,
    insert_decision,
    insert_decision_intent_order,
    insert_intent,
    insert_order,
)
from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("table", "primary_key_name", "id_key"),
    [
        (market_snapshots, "market_snapshot_id", "market_snapshot_id"),
        (candidates, "candidate_id", "candidate_id"),
        (filter_evaluations, "filter_evaluation_id", "filter_evaluation_id"),
        (trading_events, "event_id", "event_id"),
    ],
)
def test_simple_semantic_duplicate_keys_are_rejected(
    mssql_database: object,
    table: object,
    primary_key_name: str,
    id_key: str,
) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        duplicate = clone_row(
            connection,
            table,
            primary_key_name,
            ids[id_key],
            **{primary_key_name: uuid4()},
        )
        connection.execute(table.insert(), duplicate)


def test_decision_key_is_unique_independently_of_candidate_filter(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            strategy_decisions.insert(),
            {
                "decision_id": uuid4(),
                "decision_key": f"decision-{ids['suffix']}",
                "position_id": ids["position_id"],
                "market_snapshot_id": ids["market_snapshot_id"],
                "strategy_id": ids["strategy_id"],
                "strategy_version": "v2",
                "action": "EXIT_LONG",
                "reason_codes": "[]",
                "decided_at": datetime.now(UTC),
            },
        )


def test_trade_intent_idempotency_and_one_per_decision_are_enforced(
    mssql_database: object,
) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        decision_id = insert_decision(connection, ids, suffix=uuid4().hex)
        insert_intent(
            connection,
            decision_id,
            suffix=uuid4().hex,
            idempotency_key=f"intent-{ids['suffix']}",
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            trade_intents.insert(),
            clone_row(
                connection,
                trade_intents,
                "trade_intent_id",
                ids["trade_intent_id"],
                trade_intent_id=uuid4(),
                idempotency_key=uuid4().hex,
            ),
        )


def test_order_unique_keys_and_nullable_broker_reference(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        decision_id = insert_decision(connection, ids, suffix=uuid4().hex)
        intent_id = insert_intent(connection, decision_id, suffix=uuid4().hex)
        insert_order(
            connection,
            intent_id,
            suffix=uuid4().hex,
            client_order_id=ids["client_order_id"],
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            paper_orders.insert(),
            clone_row(
                connection,
                paper_orders,
                "order_id",
                ids["order_id"],
                order_id=uuid4(),
                client_order_id=uuid4(),
                broker_order_ref=None,
            ),
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        decision_id = insert_decision(connection, ids, suffix=uuid4().hex)
        intent_id = insert_intent(connection, decision_id, suffix=uuid4().hex)
        insert_order(
            connection,
            intent_id,
            suffix=uuid4().hex,
            broker_order_ref=f"broker-{ids['suffix']}",
        )

    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        for _ in range(2):
            decision_id = insert_decision(connection, ids, suffix=uuid4().hex)
            intent_id = insert_intent(connection, decision_id, suffix=uuid4().hex)
            insert_order(connection, intent_id, suffix=uuid4().hex, broker_order_ref=None)


def test_fill_execution_and_order_sequence_keys_are_unique(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        _, _, order_id = insert_decision_intent_order(connection, ids, suffix=uuid4().hex)
        connection.execute(
            paper_fills.insert(),
            {
                "fill_id": uuid4(),
                "order_id": order_id,
                "execution_key": f"execution-{ids['suffix']}",
                "fill_sequence": 1,
                "quantity": 1,
                "price": Decimal("1"),
                "fee_amount": Decimal("0"),
                "fee_currency": "USD",
                "executed_at": datetime.now(UTC),
            },
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            paper_fills.insert(),
            clone_row(
                connection,
                paper_fills,
                "fill_id",
                ids["fill_id"],
                fill_id=uuid4(),
                execution_key=uuid4().hex,
            ),
        )


def test_position_event_fill_and_position_sequence_keys_are_unique(
    mssql_database: object,
) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            position_events.insert(),
            clone_row(
                connection,
                position_events,
                "position_event_id",
                ids["position_event_id"],
                position_event_id=uuid4(),
                sequence_no=2,
            ),
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        _, _, order_id = insert_decision_intent_order(connection, ids, suffix=uuid4().hex)
        fill_id = uuid4()
        connection.execute(
            paper_fills.insert(),
            {
                "fill_id": fill_id,
                "order_id": order_id,
                "execution_key": uuid4().hex,
                "fill_sequence": 1,
                "quantity": 1,
                "price": Decimal("1"),
                "fee_amount": Decimal("0"),
                "fee_currency": "USD",
                "executed_at": datetime.now(UTC),
            },
        )
        connection.execute(
            position_events.insert(),
            clone_row(
                connection,
                position_events,
                "position_event_id",
                ids["position_event_id"],
                position_event_id=uuid4(),
                fill_id=fill_id,
            ),
        )


def test_equity_strategy_currency_as_of_is_unique(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            equity_snapshots.insert(),
            clone_row(
                connection,
                equity_snapshots,
                "equity_snapshot_id",
                ids["equity_snapshot_id"],
                equity_snapshot_id=uuid4(),
                snapshot_key=uuid4().hex,
            ),
        )


def test_equity_snapshot_key_is_unique_independently(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            equity_snapshots.insert(),
            clone_row(
                connection,
                equity_snapshots,
                "equity_snapshot_id",
                ids["equity_snapshot_id"],
                equity_snapshot_id=uuid4(),
                strategy_id=uuid4(),
                as_of=datetime.now(UTC),
            ),
        )
