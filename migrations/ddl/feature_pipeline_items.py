"""Additive DDL for immutable P3 per-symbol pipeline item records."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(
        sql,
        name=f"ck_daily_feature_pipeline_items_{suffix}",
    )


def create_daily_feature_pipeline_items_table(op: Operations) -> None:
    """Create only trading.daily_feature_pipeline_items."""

    table = "daily_feature_pipeline_items"
    op.create_table(
        "daily_feature_pipeline_items",
        sa.Column("daily_feature_pipeline_item_id", uuid_type(), nullable=False),
        sa.Column("daily_feature_pipeline_run_id", uuid_type(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("mic_code", code_type(4), nullable=False),
        sa.Column("completed_session_date", sa.Date(), nullable=True),
        sa.Column("outcome", code_type(32), nullable=False),
        sa.Column("daily_bar_created_count", sa.Integer(), nullable=False),
        sa.Column("daily_bar_existing_count", sa.Integer(), nullable=False),
        sa.Column("feature_snapshot_id", uuid_type(), nullable=True),
        sa.Column("feature_quality_status", code_type(16), nullable=True),
        sa.Column("safe_reason_code", code_type(96), nullable=True),
        sa.Column("provider_request_count", sa.Integer(), nullable=False),
        sa.Column("provider_credit_count", sa.Integer(), nullable=True),
        sa.Column("started_at", timestamp_type(), nullable=False),
        sa.Column("finished_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_pipeline_item_id",
            name="pk_daily_feature_pipeline_items",
        ),
        sa.ForeignKeyConstraint(
            ["daily_feature_pipeline_run_id"],
            ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
            name="fk_daily_feature_pipeline_items_daily_feature_pipeline_run_id_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["trading.feature_snapshots.feature_snapshot_id"],
            name="fk_daily_feature_pipeline_items_feature_snapshot_id_feature_snapshots",
            ondelete="NO ACTION",
        ),
        _check("ordinal BETWEEN 1 AND 100", "ordinal"),
        _check(symbol_check(), "symbol"),
        _check("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", "mic_code"),
        _check(
            "outcome IN ('READY','DEGRADED','DATA_INSUFFICIENT','NO_DATA',"
            "'PROVIDER_ERROR','CALENDAR_ERROR','NOT_ATTEMPTED_BUDGET',"
            "'NOT_ATTEMPTED_ABORTED')",
            "outcome",
        ),
        _check(
            "daily_bar_created_count >= 0 AND daily_bar_existing_count >= 0 "
            "AND provider_request_count >= 0 "
            "AND (provider_credit_count IS NULL OR provider_credit_count >= 0)",
            "counts_nonnegative",
        ),
        _check(
            "(outcome = 'READY' AND feature_snapshot_id IS NOT NULL "
            "AND feature_quality_status = 'READY') OR "
            "(outcome = 'DEGRADED' AND feature_snapshot_id IS NOT NULL "
            "AND feature_quality_status = 'DEGRADED') OR "
            "(outcome NOT IN ('READY','DEGRADED') AND feature_snapshot_id IS NULL "
            "AND feature_quality_status IS NULL)",
            "feature_shape",
        ),
        _check("started_at <= finished_at", "time_order"),
        sa.UniqueConstraint(
            "daily_feature_pipeline_run_id",
            "ordinal",
            name="uq_daily_feature_pipeline_items_run_ordinal",
        ),
        sa.UniqueConstraint(
            "daily_feature_pipeline_run_id",
            "symbol",
            name="uq_daily_feature_pipeline_items_run_symbol",
        ),
        sa.UniqueConstraint(
            "daily_feature_pipeline_run_id",
            "symbol",
            "mic_code",
            name="uq_daily_feature_pipeline_items_run_symbol_mic",
        ),
        schema=SCHEMA,
    )
    indexes = (
        (
            "ix_daily_feature_pipeline_items_run_outcome",
            ["daily_feature_pipeline_run_id", "outcome"],
        ),
        ("ix_daily_feature_pipeline_items_symbol_session", ["symbol", "completed_session_date"]),
        ("ix_daily_feature_pipeline_items_feature_snapshot", ["feature_snapshot_id"]),
        ("ix_daily_feature_pipeline_items_outcome_recorded", ["outcome", "recorded_at"]),
    )
    for name, columns in indexes:
        op.create_index(name, table, columns, schema=SCHEMA)
