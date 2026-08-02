"""Additive DDL for immutable P4B.1 raw forward outcomes."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    decimal_type,
    json_array_check,
    json_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)

TABLE = "daily_feature_outcomes"


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{TABLE}_{suffix}")


def create_daily_feature_outcomes_table(op: Operations) -> None:
    """Create only trading.daily_feature_outcomes."""

    op.create_table(
        "daily_feature_outcomes",
        sa.Column("daily_feature_outcome_id", uuid_type(), nullable=False),
        sa.Column("outcome_key", code_type(89), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("path_revision_digest", code_type(64), nullable=False),
        sa.Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
        sa.Column("feature_snapshot_id", uuid_type(), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("mic_code", code_type(4), nullable=False),
        sa.Column("provider_code", code_type(64), nullable=False),
        sa.Column("calendar_code", code_type(64), nullable=False),
        sa.Column("calendar_version", code_type(64), nullable=False),
        sa.Column("source_session_date", sa.Date(), nullable=False),
        sa.Column("terminal_session_date", sa.Date(), nullable=False),
        sa.Column("horizon_trading_days", sa.SmallInteger(), nullable=False),
        sa.Column("outcome_policy_code", code_type(64), nullable=False),
        sa.Column("outcome_policy_version", code_type(64), nullable=False),
        sa.Column("observation_as_of", timestamp_type(), nullable=False),
        sa.Column("reference_close", decimal_type(), nullable=False),
        sa.Column("terminal_close", decimal_type(), nullable=False),
        sa.Column("forward_close_return", decimal_type(), nullable=False),
        sa.Column("maximum_favorable_excursion_rate", decimal_type(), nullable=False),
        sa.Column("maximum_adverse_excursion_rate", decimal_type(), nullable=False),
        sa.Column("future_bar_count", sa.SmallInteger(), nullable=False),
        sa.Column("future_bar_provenance", json_type(), nullable=False),
        sa.Column("latest_input_available_at", timestamp_type(), nullable=False),
        sa.Column("observation_mode", code_type(32), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_outcome_id",
            name="pk_daily_feature_outcomes",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_run_id"],
            ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
            name="fk_daily_feature_outcomes_source_scoring_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_item_id"],
            ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
            name="fk_daily_feature_outcomes_source_scoring_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_run_id"],
            ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
            name="fk_daily_feature_outcomes_source_pipeline_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_item_id"],
            ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
            name="fk_daily_feature_outcomes_source_pipeline_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["trading.feature_snapshots.feature_snapshot_id"],
            name="fk_daily_feature_outcomes_feature_snapshot_snapshots",
            ondelete="NO ACTION",
        ),
        _check(symbol_check(), "symbol"),
        _check("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", "mic"),
        _check("provider_code = 'TWELVE_DATA_TIME_SERIES'", "provider"),
        _check(
            "calendar_code = 'US_EQUITY_CORE' AND calendar_version = '2026.v1'",
            "calendar",
        ),
        _check(
            "outcome_policy_code = 'US_EQUITY_FORWARD_PATH_OBSERVATION' "
            "AND outcome_policy_version = 'v1'",
            "policy",
        ),
        _check("source_session_date < terminal_session_date", "session_order"),
        _check("horizon_trading_days BETWEEN 1 AND 5", "horizon"),
        _check("future_bar_count = horizon_trading_days", "bar_count"),
        _check("reference_close > 0 AND terminal_close > 0", "prices"),
        _check(
            "maximum_adverse_excursion_rate <= forward_close_return "
            "AND forward_close_return <= maximum_favorable_excursion_rate",
            "rate_order",
        ),
        _check(json_array_check("future_bar_provenance"), "provenance_json"),
        _check(
            "latest_input_available_at <= observation_as_of "
            "AND observation_as_of <= generated_at AND generated_at <= recorded_at",
            "time_order",
        ),
        _check(
            "observation_mode IN ('PROSPECTIVE','RETROSPECTIVE_REPLAY')",
            "mode",
        ),
        _check(
            "DATALENGTH(outcome_key) = 89 "
            "AND outcome_key LIKE 'daily-feature-outcome:v1:%' "
            "AND RIGHT(outcome_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "outcome_key_format",
        ),
        _check(
            "DATALENGTH(content_digest) = 64 AND content_digest "
            "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        _check(
            "DATALENGTH(path_revision_digest) = 64 AND path_revision_digest "
            "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            "path_revision_digest_format",
        ),
        sa.UniqueConstraint("outcome_key", name="uq_daily_feature_outcomes_key"),
        sa.UniqueConstraint(
            "source_daily_feature_scoring_item_id",
            "outcome_policy_code",
            "outcome_policy_version",
            "path_revision_digest",
            name="uq_daily_feature_outcomes_source_item_policy_path",
        ),
        schema=SCHEMA,
    )
    for name, columns in (
        (
            "ix_daily_feature_outcomes_source_item_available",
            ["source_daily_feature_scoring_item_id", "latest_input_available_at"],
        ),
        ("ix_daily_feature_outcomes_source_run", ["source_daily_feature_scoring_run_id"]),
        ("ix_daily_feature_outcomes_symbol_terminal", ["symbol", "terminal_session_date"]),
        (
            "ix_daily_feature_outcomes_mode_terminal",
            ["observation_mode", "terminal_session_date"],
        ),
        ("ix_daily_feature_outcomes_snapshot", ["feature_snapshot_id"]),
        (
            "ix_daily_feature_outcomes_provider_terminal",
            ["provider_code", "terminal_session_date"],
        ),
    ):
        op.create_index(name, TABLE, columns, schema=SCHEMA)
