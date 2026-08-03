"""Additive 0002 migration compatibility and round-trip checks."""

from __future__ import annotations

from sqlalchemy import inspect, select, text

from auto_trading_v2.adapters.persistence.tables import strategy_decisions
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.persistence.records import insert_canonical_graph


def test_candidate_rows_survive_0001_to_0002_and_downgrade_round_trip(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    assert mssql_database.name.startswith("auto_trading_v2_test_")
    mssql_database.run_downgrade("0001_mssql_schema")
    try:
        with mssql_database.engine.begin() as connection:
            ids = insert_canonical_graph(connection)

        mssql_database.run_upgrade("head")
        inspector = inspect(mssql_database.engine)
        columns = {
            column["name"]
            for column in inspector.get_columns("strategy_decisions", schema="trading")
        }
        foreign_keys = {
            item["name"]: item
            for item in inspector.get_foreign_keys("strategy_decisions", schema="trading")
        }
        indexes = {
            item["name"]: item
            for item in inspector.get_indexes("strategy_decisions", schema="trading")
        }
        with mssql_database.engine.connect() as connection:
            snapshot_id = connection.execute(
                select(strategy_decisions.c.market_snapshot_id).where(
                    strategy_decisions.c.decision_id == ids["decision_id"]
                )
            ).scalar_one()

        assert snapshot_id is None
        assert "market_snapshot_id" in columns
        assert "fk_strategy_decisions_market_snapshot_id_market_snapshots" in foreign_keys
        assert foreign_keys["fk_strategy_decisions_market_snapshot_id_market_snapshots"][
            "options"
        ].get("ondelete") in {None, "NO ACTION"}
        assert "ix_strategy_decisions_position_snapshot_unique" in indexes

        mssql_database.run_downgrade("0001_mssql_schema")
        inspector = inspect(mssql_database.engine)
        downgraded_columns = {
            column["name"]
            for column in inspector.get_columns("strategy_decisions", schema="trading")
        }
        downgraded_foreign_keys = {
            item["name"]
            for item in inspector.get_foreign_keys("strategy_decisions", schema="trading")
        }
        downgraded_indexes = {
            item["name"] for item in inspector.get_indexes("strategy_decisions", schema="trading")
        }
        with mssql_database.engine.connect() as connection:
            preserved = connection.execute(
                text(
                    "SELECT COUNT(*) FROM trading.strategy_decisions "
                    "WHERE decision_id = :decision_id"
                ),
                {"decision_id": ids["decision_id"]},
            ).scalar_one()

        assert preserved == 1
        assert "market_snapshot_id" not in downgraded_columns
        assert "fk_strategy_decisions_market_snapshot_id_market_snapshots" not in (
            downgraded_foreign_keys
        )
        assert "ix_strategy_decisions_position_snapshot_unique" not in downgraded_indexes
        assert "ix_strategy_decisions_position" in downgraded_indexes
    finally:
        mssql_database.run_upgrade("head")
        mssql_database.run_check()
