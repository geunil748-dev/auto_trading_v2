from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    filter_evaluations,
    market_snapshots,
    paper_fills,
    paper_orders,
    position_events,
    strategy_decisions,
    trade_intents,
    trading_events,
)

from .helpers import clone_row
from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("table", "primary_key_name", "id_key", "foreign_key_name"),
    [
        (candidates, "candidate_id", "candidate_id", "market_snapshot_id"),
        (
            filter_evaluations,
            "filter_evaluation_id",
            "filter_evaluation_id",
            "candidate_id",
        ),
        (trade_intents, "trade_intent_id", "trade_intent_id", "decision_id"),
        (paper_orders, "order_id", "order_id", "trade_intent_id"),
        (paper_fills, "fill_id", "fill_id", "order_id"),
        (position_events, "position_event_id", "position_event_id", "fill_id"),
        (trading_events, "event_id", "event_id", "market_snapshot_id"),
    ],
)
def test_missing_foreign_rows_are_rejected(
    mssql_database: object,
    table: object,
    primary_key_name: str,
    id_key: str,
    foreign_key_name: str,
) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        invalid = clone_row(
            connection,
            table,
            primary_key_name,
            ids[id_key],
            **{
                primary_key_name: uuid4(),
                foreign_key_name: uuid4(),
            },
        )
        if table is trading_events:
            invalid["dedup_key"] = uuid4().hex
        connection.execute(table.insert(), invalid)


@pytest.mark.parametrize("reference_kind", ["candidate", "position"])
def test_decision_requires_an_existing_candidate_or_position(
    mssql_database: object, reference_kind: str
) -> None:
    values = {
        "decision_id": uuid4(),
        "decision_key": uuid4().hex,
        "candidate_id": uuid4() if reference_kind == "candidate" else None,
        "position_id": uuid4() if reference_kind == "position" else None,
        "market_snapshot_id": uuid4() if reference_kind == "position" else None,
        "strategy_id": uuid4(),
        "strategy_version": "v1",
        "action": "OBSERVE",
        "reason_codes": "[]",
        "decided_at": datetime.now(UTC),
    }
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(strategy_decisions.insert(), values)


def test_referenced_canonical_parent_cannot_be_deleted(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            market_snapshots.delete().where(
                market_snapshots.c.market_snapshot_id == ids["market_snapshot_id"]
            )
        )
