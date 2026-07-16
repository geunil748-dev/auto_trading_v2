"""Guarded 0003 position-version migration and MSSQL constraint checks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from auto_trading_v2.adapters.persistence.tables import strategy_decisions
from tests.integration.persistence.conftest import temporary_mssql_database
from tests.integration.persistence.records import insert_canonical_graph

pytestmark = pytest.mark.integration


def _position_decision(ids: dict[str, object], **changes: object) -> dict[str, object]:
    values = {
        "decision_id": uuid4(),
        "decision_key": f"position-version-{uuid4().hex}",
        "candidate_id": None,
        "position_id": ids["position_id"],
        "position_version": 1,
        "market_snapshot_id": ids["market_snapshot_id"],
        "filter_evaluation_id": None,
        "strategy_id": ids["strategy_id"],
        "strategy_version": "v1",
        "action": "EXIT_LONG",
        "reason_codes": json.dumps(["TEST"]),
        "decided_at": datetime.now(UTC),
    }
    values.update(changes)
    return values


def test_0002_to_0003_preserves_candidates_and_round_trips() -> None:
    with temporary_mssql_database() as database:
        database.run_downgrade("0002_position_snapshot")
        with database.engine.begin() as connection:
            ids = insert_canonical_graph(connection)

        database.run_upgrade("head")
        inspector = inspect(database.engine)
        columns = {
            item["name"] for item in inspector.get_columns("strategy_decisions", schema="trading")
        }
        foreign_keys = {
            item["name"]: item
            for item in inspector.get_foreign_keys("strategy_decisions", schema="trading")
        }
        indexes = {
            item["name"] for item in inspector.get_indexes("strategy_decisions", schema="trading")
        }
        with database.engine.connect() as connection:
            checks = set(
                connection.execute(
                    text(
                        "SELECT cc.name FROM sys.check_constraints cc "
                        "JOIN sys.tables t ON cc.parent_object_id = t.object_id "
                        "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                        "WHERE s.name = 'trading' AND t.name = 'strategy_decisions'"
                    )
                ).scalars()
            )
            candidate_version = connection.execute(
                select(strategy_decisions.c.position_version).where(
                    strategy_decisions.c.decision_id == ids["decision_id"]
                )
            ).scalar_one()

        assert candidate_version is None
        assert "position_version" in columns
        assert "fk_strategy_decisions_position_version_position_events" in foreign_keys
        assert foreign_keys["fk_strategy_decisions_position_version_position_events"][
            "options"
        ].get("ondelete") in {None, "NO ACTION"}
        assert "ix_strategy_decisions_position_version" in indexes
        assert {
            "ck_strategy_decisions_candidate_without_position_version",
            "ck_strategy_decisions_position_requires_version",
            "ck_strategy_decisions_position_version_positive",
        }.issubset(checks)

        with database.engine.connect() as connection:
            transaction = connection.begin()
            values = _position_decision(ids)
            decision_id = values["decision_id"]
            connection.execute(strategy_decisions.insert(), values)
            stored_version = connection.execute(
                select(strategy_decisions.c.position_version).where(
                    strategy_decisions.c.decision_id == decision_id
                )
            ).scalar_one()
            assert stored_version == 1
            transaction.rollback()

        for changes in (
            {"position_version": None},
            {"position_version": 0},
            {"position_version": 2},
            {
                "candidate_id": ids["candidate_id"],
                "position_id": None,
                "position_version": 1,
                "market_snapshot_id": None,
                "filter_evaluation_id": ids["filter_evaluation_id"],
                "strategy_id": uuid4(),
            },
        ):
            with pytest.raises(IntegrityError), database.engine.begin() as connection:
                connection.execute(
                    strategy_decisions.insert(),
                    _position_decision(ids, **changes),
                )

        database.run_downgrade("0002_position_snapshot")
        inspector = inspect(database.engine)
        downgraded_columns = {
            item["name"] for item in inspector.get_columns("strategy_decisions", schema="trading")
        }
        downgraded_foreign_keys = {
            item["name"]
            for item in inspector.get_foreign_keys("strategy_decisions", schema="trading")
        }
        downgraded_indexes = {
            item["name"] for item in inspector.get_indexes("strategy_decisions", schema="trading")
        }
        assert "position_version" not in downgraded_columns
        assert "fk_strategy_decisions_position_version_position_events" not in (
            downgraded_foreign_keys
        )
        assert "ix_strategy_decisions_position_version" not in downgraded_indexes

        database.run_upgrade("head")
        database.run_check()


def test_0003_blocks_existing_position_decisions_without_guessing_backfill() -> None:
    with temporary_mssql_database() as database:
        database.run_downgrade("0002_position_snapshot")
        with database.engine.begin() as connection:
            ids = insert_canonical_graph(connection)
            decision_id = uuid4()
            values = _position_decision(ids)
            values.pop("position_version")
            values["decision_id"] = decision_id
            connection.execute(strategy_decisions.insert(), values)

        with pytest.raises(DBAPIError) as captured:
            database.run_upgrade("head")

        rendered = str(captured.value)
        assert "existing position decisions require explicit backfill" in rendered
        assert str(decision_id) not in rendered
        with database.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM trading.strategy_decisions WHERE decision_id = :decision_id"),
                {"decision_id": decision_id},
            )
        database.run_upgrade("head")
        database.run_check()
