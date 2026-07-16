"""MSSQL source-shape and semantic defenses for position decisions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import strategy_decisions
from tests.integration.persistence.records import insert_canonical_graph

pytestmark = pytest.mark.integration


def _position_values(ids: dict[str, object], **changes: object) -> dict[str, object]:
    values = {
        "decision_id": uuid4(),
        "decision_key": f"position-{uuid4().hex}",
        "candidate_id": None,
        "position_id": ids["position_id"],
        "market_snapshot_id": ids["market_snapshot_id"],
        "filter_evaluation_id": None,
        "strategy_id": ids["strategy_id"],
        "strategy_version": "v1",
        "action": "EXIT_LONG",
        "reason_codes": json.dumps(["POSITION_EXIT_ALLOWED"]),
        "decided_at": datetime.now(UTC),
    }
    values.update(changes)
    return values


@pytest.mark.parametrize(
    "changes",
    [
        {"market_snapshot_id": None},
        {"candidate_id": uuid4()},
        {"filter_evaluation_id": uuid4()},
    ],
)
def test_invalid_position_source_shapes_are_rejected(
    mssql_database: object,
    changes: dict[str, object],
) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        if "candidate_id" in changes:
            changes["candidate_id"] = ids["candidate_id"]
        if "filter_evaluation_id" in changes:
            changes["filter_evaluation_id"] = ids["filter_evaluation_id"]
        connection.execute(
            strategy_decisions.insert(),
            _position_values(ids, **changes),
        )


def test_candidate_cannot_duplicate_market_snapshot_source(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            strategy_decisions.insert(),
            {
                "decision_id": uuid4(),
                "decision_key": f"candidate-{uuid4().hex}",
                "candidate_id": ids["candidate_id"],
                "market_snapshot_id": ids["market_snapshot_id"],
                "filter_evaluation_id": ids["filter_evaluation_id"],
                "strategy_id": uuid4(),
                "strategy_version": "v1",
                "action": "SKIP",
                "reason_codes": json.dumps(["ENTRY_BLOCKED"]),
                "decided_at": datetime.now(UTC),
            },
        )
