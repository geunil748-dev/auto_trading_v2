"""Canonical immutable P3 daily feature pipeline run and item tables."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    Table,
    UniqueConstraint,
)

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    non_empty_check_sql,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

daily_feature_pipeline_runs = Table(
    "daily_feature_pipeline_runs",
    metadata,
    Column("daily_feature_pipeline_run_id", uuid_type(), primary_key=True),
    Column("run_key", code_type(85), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("universe_snapshot_id", uuid_type(), nullable=False),
    Column("pipeline_code", code_type(64), nullable=False),
    Column("pipeline_version", code_type(64), nullable=False),
    Column("provider_code", code_type(64), nullable=False),
    Column("calendar_code", code_type(64), nullable=False),
    Column("calendar_version", code_type(64), nullable=False),
    Column("completed_session_date", Date(), nullable=True),
    Column("as_of", timestamp_type(), nullable=False),
    Column("completion_grace_seconds", Integer(), nullable=False),
    Column("adjustment_basis", code_type(16), nullable=False),
    Column("feature_set_code", code_type(64), nullable=False),
    Column("feature_set_version", code_type(64), nullable=False),
    Column("horizon_trading_days", SmallInteger(), nullable=False),
    Column("requested_session_count", Integer(), nullable=False),
    Column("status", code_type(40), nullable=False),
    Column("total_count", SmallInteger(), nullable=False),
    Column("ready_count", SmallInteger(), nullable=False),
    Column("degraded_count", SmallInteger(), nullable=False),
    Column("data_insufficient_count", SmallInteger(), nullable=False),
    Column("no_data_count", SmallInteger(), nullable=False),
    Column("provider_error_count", SmallInteger(), nullable=False),
    Column("calendar_error_count", SmallInteger(), nullable=False),
    Column("not_attempted_count", SmallInteger(), nullable=False),
    Column("estimated_credit_count", Integer(), nullable=True),
    Column("consumed_credit_count", Integer(), nullable=True),
    Column("started_at", timestamp_type(), nullable=False),
    Column("finished_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["universe_snapshot_id"],
        ["trading.universe_snapshots.universe_snapshot_id"],
        name="fk_daily_feature_pipeline_runs_universe_snapshot_id_universe_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint(non_empty_check_sql("pipeline_code"), name="pipeline_code_nonempty"),
    CheckConstraint(non_empty_check_sql("pipeline_version"), name="pipeline_version_nonempty"),
    CheckConstraint(non_empty_check_sql("provider_code"), name="provider_code_nonempty"),
    CheckConstraint("horizon_trading_days BETWEEN 1 AND 5", name="horizon"),
    CheckConstraint("requested_session_count >= 21", name="requested_sessions"),
    CheckConstraint("completion_grace_seconds BETWEEN 0 AND 86400", name="completion_grace"),
    CheckConstraint("adjustment_basis = 'SPLIT_ADJUSTED'", name="adjustment_basis"),
    CheckConstraint(
        "status IN ('COMPLETED','COMPLETED_WITH_WARNINGS',"
        "'COMPLETED_WITH_PARTIAL_FAILURES','NO_COMPLETED_SESSION',"
        "'BUDGET_BLOCKED','ABORTED_PROVIDER_FATAL')",
        name="status",
    ),
    CheckConstraint(
        "total_count >= 0 AND ready_count >= 0 AND degraded_count >= 0 "
        "AND data_insufficient_count >= 0 AND no_data_count >= 0 "
        "AND provider_error_count >= 0 AND calendar_error_count >= 0 "
        "AND not_attempted_count >= 0",
        name="counts_nonnegative",
    ),
    CheckConstraint(
        "total_count = ready_count + degraded_count + data_insufficient_count "
        "+ no_data_count + provider_error_count + calendar_error_count "
        "+ not_attempted_count",
        name="count_sum",
    ),
    CheckConstraint(
        "estimated_credit_count IS NULL OR estimated_credit_count >= 0",
        name="estimated_credits",
    ),
    CheckConstraint(
        "consumed_credit_count IS NULL OR consumed_credit_count >= 0",
        name="consumed_credits",
    ),
    CheckConstraint("started_at <= finished_at", name="time_order"),
    CheckConstraint(
        "DATALENGTH(run_key) = 85 AND run_key LIKE 'daily-feature-run:v1:%' "
        "AND RIGHT(run_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="run_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 AND content_digest "
        "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("run_key", name="uq_daily_feature_pipeline_runs_run_key"),
    schema=SCHEMA,
)

daily_feature_pipeline_items = Table(
    "daily_feature_pipeline_items",
    metadata,
    Column("daily_feature_pipeline_item_id", uuid_type(), primary_key=True),
    Column("daily_feature_pipeline_run_id", uuid_type(), nullable=False),
    Column("ordinal", SmallInteger(), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("mic_code", code_type(4), nullable=False),
    Column("completed_session_date", Date(), nullable=True),
    Column("outcome", code_type(32), nullable=False),
    Column("daily_bar_created_count", Integer(), nullable=False),
    Column("daily_bar_existing_count", Integer(), nullable=False),
    Column("feature_snapshot_id", uuid_type(), nullable=True),
    Column("feature_quality_status", code_type(16), nullable=True),
    Column("safe_reason_code", code_type(96), nullable=True),
    Column("provider_request_count", Integer(), nullable=False),
    Column("provider_credit_count", Integer(), nullable=True),
    Column("started_at", timestamp_type(), nullable=False),
    Column("finished_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["daily_feature_pipeline_run_id"],
        ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
        name="fk_daily_feature_pipeline_items_daily_feature_pipeline_run_id_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["feature_snapshot_id"],
        ["trading.feature_snapshots.feature_snapshot_id"],
        name="fk_daily_feature_pipeline_items_feature_snapshot_id_feature_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint("ordinal BETWEEN 1 AND 100", name="ordinal"),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", name="mic_code"),
    CheckConstraint(
        "outcome IN ('READY','DEGRADED','DATA_INSUFFICIENT','NO_DATA',"
        "'PROVIDER_ERROR','CALENDAR_ERROR','NOT_ATTEMPTED_BUDGET',"
        "'NOT_ATTEMPTED_ABORTED')",
        name="outcome",
    ),
    CheckConstraint(
        "daily_bar_created_count >= 0 AND daily_bar_existing_count >= 0 "
        "AND provider_request_count >= 0 "
        "AND (provider_credit_count IS NULL OR provider_credit_count >= 0)",
        name="counts_nonnegative",
    ),
    CheckConstraint(
        "(outcome = 'READY' AND feature_snapshot_id IS NOT NULL "
        "AND feature_quality_status = 'READY') OR "
        "(outcome = 'DEGRADED' AND feature_snapshot_id IS NOT NULL "
        "AND feature_quality_status = 'DEGRADED') OR "
        "(outcome NOT IN ('READY','DEGRADED') AND feature_snapshot_id IS NULL "
        "AND feature_quality_status IS NULL)",
        name="feature_shape",
    ),
    CheckConstraint("started_at <= finished_at", name="time_order"),
    UniqueConstraint(
        "daily_feature_pipeline_run_id",
        "ordinal",
        name="uq_daily_feature_pipeline_items_run_ordinal",
    ),
    UniqueConstraint(
        "daily_feature_pipeline_run_id",
        "symbol",
        name="uq_daily_feature_pipeline_items_run_symbol",
    ),
    UniqueConstraint(
        "daily_feature_pipeline_run_id",
        "symbol",
        "mic_code",
        name="uq_daily_feature_pipeline_items_run_symbol_mic",
    ),
    schema=SCHEMA,
)

Index("ix_daily_feature_pipeline_runs_universe", daily_feature_pipeline_runs.c.universe_snapshot_id)
Index(
    "ix_daily_feature_pipeline_runs_provider_session",
    daily_feature_pipeline_runs.c.provider_code,
    daily_feature_pipeline_runs.c.completed_session_date,
)
Index(
    "ix_daily_feature_pipeline_runs_status_started",
    daily_feature_pipeline_runs.c.status,
    daily_feature_pipeline_runs.c.started_at,
)
Index(
    "ix_daily_feature_pipeline_runs_completed_session",
    daily_feature_pipeline_runs.c.completed_session_date,
)
Index("ix_daily_feature_pipeline_runs_as_of", daily_feature_pipeline_runs.c.as_of)
Index(
    "ix_daily_feature_pipeline_items_run_outcome",
    daily_feature_pipeline_items.c.daily_feature_pipeline_run_id,
    daily_feature_pipeline_items.c.outcome,
)
Index(
    "ix_daily_feature_pipeline_items_symbol_session",
    daily_feature_pipeline_items.c.symbol,
    daily_feature_pipeline_items.c.completed_session_date,
)
Index(
    "ix_daily_feature_pipeline_items_feature_snapshot",
    daily_feature_pipeline_items.c.feature_snapshot_id,
)
Index(
    "ix_daily_feature_pipeline_items_outcome_recorded",
    daily_feature_pipeline_items.c.outcome,
    daily_feature_pipeline_items.c.recorded_at,
)
