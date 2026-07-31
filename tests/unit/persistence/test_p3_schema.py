from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
    universe_snapshots,
)


def columns(table: object, kind: type) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, kind)
    }


def checks(table: object) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def indexes(table: object) -> set[tuple[str, ...]]:
    return {tuple(column.name for column in index.columns) for index in table.indexes}


def test_universe_table_has_exact_identity_json_and_indexes() -> None:
    assert isinstance(universe_snapshots.c.universe_snapshot_id.type, mssql.UNIQUEIDENTIFIER)
    assert isinstance(universe_snapshots.c.members.type, mssql.NVARCHAR)
    assert universe_snapshots.c.members.type.length is None
    assert ("universe_key",) in columns(universe_snapshots, UniqueConstraint)
    assert ("universe_code", "universe_version") in columns(universe_snapshots, UniqueConstraint)
    assert {("universe_code", "universe_version"), ("generated_at",)} == indexes(universe_snapshots)
    sql = checks(universe_snapshots)
    assert "member_count BETWEEN 1 AND 100" in sql
    assert "ISJSON(members) = 1" in sql
    assert "members <> '[]'" in sql


def test_run_table_has_exact_fk_counts_status_and_indexes() -> None:
    foreign_keys = {
        tuple(column.name for column in constraint.columns): constraint.ondelete
        for constraint in daily_feature_pipeline_runs.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert foreign_keys == {("universe_snapshot_id",): "NO ACTION"}
    assert ("run_key",) in columns(daily_feature_pipeline_runs, UniqueConstraint)
    sql = checks(daily_feature_pipeline_runs)
    assert "requested_session_count >= 21" in sql
    assert "total_count = ready_count" in sql
    assert "ABORTED_PROVIDER_FATAL" in sql
    assert "adjustment_basis = 'SPLIT_ADJUSTED'" in sql
    assert indexes(daily_feature_pipeline_runs) == {
        ("universe_snapshot_id",),
        ("provider_code", "completed_session_date"),
        ("status", "started_at"),
        ("completed_session_date",),
        ("as_of",),
    }


def test_item_table_has_exact_fks_shape_uniques_and_indexes() -> None:
    foreign_keys = {
        tuple(column.name for column in constraint.columns): constraint.ondelete
        for constraint in daily_feature_pipeline_items.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert foreign_keys == {
        ("daily_feature_pipeline_run_id",): "NO ACTION",
        ("feature_snapshot_id",): "NO ACTION",
    }
    assert columns(daily_feature_pipeline_items, UniqueConstraint) >= {
        ("daily_feature_pipeline_run_id", "ordinal"),
        ("daily_feature_pipeline_run_id", "symbol"),
        ("daily_feature_pipeline_run_id", "symbol", "mic_code"),
    }
    sql = checks(daily_feature_pipeline_items)
    assert "ordinal BETWEEN 1 AND 100" in sql
    assert "XNGS" in sql and "XNAS" not in sql
    assert "feature_snapshot_id IS NOT NULL" in sql
    assert indexes(daily_feature_pipeline_items) == {
        ("daily_feature_pipeline_run_id", "outcome"),
        ("symbol", "completed_session_date"),
        ("feature_snapshot_id",),
        ("outcome", "recorded_at"),
    }
