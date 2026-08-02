"""Additive DDL for immutable P4B.2A positive-close labels."""

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

TABLE = "daily_feature_outcome_labels"


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{TABLE}_{suffix}")


def create_daily_feature_outcome_labels_table(op: Operations) -> None:
    op.create_table(
        "daily_feature_outcome_labels",
        sa.Column("daily_feature_outcome_label_id", uuid_type(), nullable=False),
        sa.Column("label_key", code_type(95), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("source_daily_feature_outcome_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
        sa.Column("feature_snapshot_id", uuid_type(), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("mic_code", code_type(4), nullable=False),
        sa.Column("horizon_trading_days", sa.SmallInteger(), nullable=False),
        sa.Column("source_session_date", sa.Date(), nullable=False),
        sa.Column("terminal_session_date", sa.Date(), nullable=False),
        sa.Column("observation_mode", code_type(32), nullable=False),
        sa.Column("source_path_revision_digest", code_type(64), nullable=False),
        sa.Column("label_policy_code", code_type(64), nullable=False),
        sa.Column("label_policy_version", code_type(64), nullable=False),
        sa.Column("label_value", code_type(16), nullable=False),
        sa.Column("source_latest_input_available_at", timestamp_type(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_outcome_label_id", name="pk_daily_feature_outcome_labels"
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_outcome_id"],
            ["trading.daily_feature_outcomes.daily_feature_outcome_id"],
            name="fk_daily_feature_outcome_labels_source_outcome_outcomes",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_run_id"],
            ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
            name="fk_daily_feature_outcome_labels_source_scoring_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_item_id"],
            ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
            name="fk_daily_feature_outcome_labels_source_scoring_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_run_id"],
            ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
            name="fk_daily_feature_outcome_labels_source_pipeline_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_item_id"],
            ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
            name="fk_daily_feature_outcome_labels_source_pipeline_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["trading.feature_snapshots.feature_snapshot_id"],
            name="fk_daily_feature_outcome_labels_snapshot_snapshots",
            ondelete="NO ACTION",
        ),
        _check(symbol_check(), "symbol"),
        _check("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", "mic"),
        _check("horizon_trading_days BETWEEN 1 AND 5", "horizon"),
        _check("source_session_date < terminal_session_date", "session_order"),
        _check("observation_mode IN ('PROSPECTIVE','RETROSPECTIVE_REPLAY')", "mode"),
        _check(
            "label_policy_code = 'US_EQUITY_POSITIVE_FORWARD_CLOSE_LABEL' "
            "AND label_policy_version = 'v1'",
            "policy",
        ),
        _check("label_value IN ('POSITIVE','NOT_POSITIVE')", "value"),
        _check(
            "source_latest_input_available_at <= generated_at AND generated_at <= recorded_at",
            "time_order",
        ),
        _check(
            "DATALENGTH(label_key) = 95 "
            "AND label_key LIKE 'daily-feature-outcome-label:v1:%' "
            "AND RIGHT(label_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "label_key_format",
        ),
        _check(
            "DATALENGTH(content_digest) = 64 "
            "AND content_digest COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        _check(
            "DATALENGTH(source_path_revision_digest) = 64 "
            "AND source_path_revision_digest COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "source_path_revision_digest_format",
        ),
        sa.UniqueConstraint("label_key", name="uq_daily_feature_outcome_labels_key"),
        sa.UniqueConstraint(
            "source_daily_feature_outcome_id",
            "label_policy_code",
            "label_policy_version",
            name="uq_daily_feature_outcome_labels_source_policy",
        ),
        schema=SCHEMA,
    )
    for name, columns in (
        ("ix_daily_feature_outcome_labels_source_outcome", ["source_daily_feature_outcome_id"]),
        (
            "ix_daily_feature_outcome_labels_source_item_generated",
            ["source_daily_feature_scoring_item_id", "generated_at"],
        ),
        (
            "ix_daily_feature_outcome_labels_value_terminal",
            ["label_value", "terminal_session_date"],
        ),
        (
            "ix_daily_feature_outcome_labels_mode_terminal",
            ["observation_mode", "terminal_session_date"],
        ),
    ):
        op.create_index(name, TABLE, columns, schema=SCHEMA)
