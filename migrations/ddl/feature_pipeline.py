"""Additive DDL for the P3 multi-symbol daily feature pipeline."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    json_array_check,
    json_type,
    named_check_constraint,
    timestamp_type,
    uuid_type,
)
from migrations.ddl.feature_pipeline_items import (
    create_daily_feature_pipeline_items_table,
)


def _check(table: str, sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{table}_{suffix}")


def _digest_check(column: str) -> str:
    return (
        f"DATALENGTH({column}) = 64 AND {column} COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'"
    )


def _create_universe_snapshots(op: Operations) -> None:
    table = "universe_snapshots"
    op.create_table(
        "universe_snapshots",
        sa.Column("universe_snapshot_id", uuid_type(), nullable=False),
        sa.Column("universe_key", code_type(76), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("universe_code", code_type(64), nullable=False),
        sa.Column("universe_version", code_type(64), nullable=False),
        sa.Column("member_count", sa.SmallInteger(), nullable=False),
        sa.Column("members", json_type(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("universe_snapshot_id", name="pk_universe_snapshots"),
        _check(
            table,
            "DATALENGTH(LTRIM(RTRIM(universe_code))) > 0",
            "universe_code_nonempty",
        ),
        _check(
            table,
            "DATALENGTH(LTRIM(RTRIM(universe_version))) > 0",
            "universe_version_nonempty",
        ),
        _check(table, "member_count BETWEEN 1 AND 100", "member_count"),
        _check(table, json_array_check("members"), "members_json_array"),
        _check(table, "members <> '[]'", "members_nonempty"),
        _check(table, "generated_at <= recorded_at", "time_order"),
        _check(
            table,
            "DATALENGTH(universe_key) = 76 AND universe_key LIKE 'universe:v1:%' "
            "AND RIGHT(universe_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "universe_key_format",
        ),
        _check(table, _digest_check("content_digest"), "content_digest_format"),
        sa.UniqueConstraint(
            "universe_key",
            name="uq_universe_snapshots_universe_key",
        ),
        sa.UniqueConstraint(
            "universe_code",
            "universe_version",
            name="uq_universe_snapshots_code_version",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_universe_snapshots_code_version",
        table,
        ["universe_code", "universe_version"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_universe_snapshots_generated",
        table,
        ["generated_at"],
        schema=SCHEMA,
    )


def _run_constraints(table: str) -> tuple[sa.CheckConstraint, ...]:
    return (
        _check(table, "DATALENGTH(LTRIM(RTRIM(pipeline_code))) > 0", "pipeline_code_nonempty"),
        _check(
            table,
            "DATALENGTH(LTRIM(RTRIM(pipeline_version))) > 0",
            "pipeline_version_nonempty",
        ),
        _check(table, "DATALENGTH(LTRIM(RTRIM(provider_code))) > 0", "provider_code_nonempty"),
        _check(table, "horizon_trading_days BETWEEN 1 AND 5", "horizon"),
        _check(table, "requested_session_count >= 21", "requested_sessions"),
        _check(table, "completion_grace_seconds BETWEEN 0 AND 86400", "completion_grace"),
        _check(table, "adjustment_basis = 'SPLIT_ADJUSTED'", "adjustment_basis"),
        _check(
            table,
            "status IN ('COMPLETED','COMPLETED_WITH_WARNINGS',"
            "'COMPLETED_WITH_PARTIAL_FAILURES','NO_COMPLETED_SESSION',"
            "'BUDGET_BLOCKED','ABORTED_PROVIDER_FATAL')",
            "status",
        ),
        _check(
            table,
            "total_count >= 0 AND ready_count >= 0 AND degraded_count >= 0 "
            "AND data_insufficient_count >= 0 AND no_data_count >= 0 "
            "AND provider_error_count >= 0 AND calendar_error_count >= 0 "
            "AND not_attempted_count >= 0",
            "counts_nonnegative",
        ),
        _check(
            table,
            "total_count = ready_count + degraded_count + data_insufficient_count "
            "+ no_data_count + provider_error_count + calendar_error_count "
            "+ not_attempted_count",
            "count_sum",
        ),
        _check(
            table,
            "estimated_credit_count IS NULL OR estimated_credit_count >= 0",
            "estimated_credits",
        ),
        _check(
            table,
            "consumed_credit_count IS NULL OR consumed_credit_count >= 0",
            "consumed_credits",
        ),
        _check(table, "started_at <= finished_at", "time_order"),
        _check(
            table,
            "DATALENGTH(run_key) = 85 AND run_key LIKE 'daily-feature-run:v1:%' "
            "AND RIGHT(run_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "run_key_format",
        ),
        _check(table, _digest_check("content_digest"), "content_digest_format"),
    )


def _create_daily_feature_pipeline_runs(op: Operations) -> None:
    table = "daily_feature_pipeline_runs"
    op.create_table(
        "daily_feature_pipeline_runs",
        sa.Column("daily_feature_pipeline_run_id", uuid_type(), nullable=False),
        sa.Column("run_key", code_type(85), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("universe_snapshot_id", uuid_type(), nullable=False),
        sa.Column("pipeline_code", code_type(64), nullable=False),
        sa.Column("pipeline_version", code_type(64), nullable=False),
        sa.Column("provider_code", code_type(64), nullable=False),
        sa.Column("calendar_code", code_type(64), nullable=False),
        sa.Column("calendar_version", code_type(64), nullable=False),
        sa.Column("completed_session_date", sa.Date(), nullable=True),
        sa.Column("as_of", timestamp_type(), nullable=False),
        sa.Column("completion_grace_seconds", sa.Integer(), nullable=False),
        sa.Column("adjustment_basis", code_type(16), nullable=False),
        sa.Column("feature_set_code", code_type(64), nullable=False),
        sa.Column("feature_set_version", code_type(64), nullable=False),
        sa.Column("horizon_trading_days", sa.SmallInteger(), nullable=False),
        sa.Column("requested_session_count", sa.Integer(), nullable=False),
        sa.Column("status", code_type(40), nullable=False),
        sa.Column("total_count", sa.SmallInteger(), nullable=False),
        sa.Column("ready_count", sa.SmallInteger(), nullable=False),
        sa.Column("degraded_count", sa.SmallInteger(), nullable=False),
        sa.Column("data_insufficient_count", sa.SmallInteger(), nullable=False),
        sa.Column("no_data_count", sa.SmallInteger(), nullable=False),
        sa.Column("provider_error_count", sa.SmallInteger(), nullable=False),
        sa.Column("calendar_error_count", sa.SmallInteger(), nullable=False),
        sa.Column("not_attempted_count", sa.SmallInteger(), nullable=False),
        sa.Column("estimated_credit_count", sa.Integer(), nullable=True),
        sa.Column("consumed_credit_count", sa.Integer(), nullable=True),
        sa.Column("started_at", timestamp_type(), nullable=False),
        sa.Column("finished_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_pipeline_run_id",
            name="pk_daily_feature_pipeline_runs",
        ),
        sa.ForeignKeyConstraint(
            ["universe_snapshot_id"],
            ["trading.universe_snapshots.universe_snapshot_id"],
            name="fk_daily_feature_pipeline_runs_universe_snapshot_id_universe_snapshots",
            ondelete="NO ACTION",
        ),
        *_run_constraints(table),
        sa.UniqueConstraint(
            "run_key",
            name="uq_daily_feature_pipeline_runs_run_key",
        ),
        schema=SCHEMA,
    )
    indexes = (
        ("ix_daily_feature_pipeline_runs_universe", ["universe_snapshot_id"]),
        (
            "ix_daily_feature_pipeline_runs_provider_session",
            ["provider_code", "completed_session_date"],
        ),
        ("ix_daily_feature_pipeline_runs_status_started", ["status", "started_at"]),
        ("ix_daily_feature_pipeline_runs_completed_session", ["completed_session_date"]),
        ("ix_daily_feature_pipeline_runs_as_of", ["as_of"]),
    )
    for name, columns in indexes:
        op.create_index(name, table, columns, schema=SCHEMA)


def create_multi_symbol_feature_pipeline_tables(op: Operations) -> None:
    """Create only the three P3 canonical tables in dependency order."""

    _create_universe_snapshots(op)
    _create_daily_feature_pipeline_runs(op)
    create_daily_feature_pipeline_items_table(op)
