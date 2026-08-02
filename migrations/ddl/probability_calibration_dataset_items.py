"""Additive DDL for immutable P4B.2A dataset items."""

import sqlalchemy as sa
from alembic.operations import Operations
from sqlalchemy.dialects import mssql

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

TABLE = "probability_calibration_dataset_items"


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{TABLE}_{suffix}")


def create_probability_calibration_dataset_items_table(op: Operations) -> None:
    op.create_table(
        "probability_calibration_dataset_items",
        sa.Column("probability_calibration_dataset_item_id", uuid_type(), nullable=False),
        sa.Column("probability_calibration_dataset_id", uuid_type(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_daily_feature_outcome_label_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_outcome_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
        sa.Column("feature_snapshot_id", uuid_type(), nullable=False),
        sa.Column("source_outcome_key", code_type(89), nullable=False),
        sa.Column("source_outcome_content_digest", code_type(64), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("mic_code", code_type(4), nullable=False),
        sa.Column("horizon_trading_days", sa.SmallInteger(), nullable=False),
        sa.Column("source_session_date", sa.Date(), nullable=False),
        sa.Column("terminal_session_date", sa.Date(), nullable=False),
        sa.Column("observation_mode", code_type(32), nullable=False),
        sa.Column("source_quality_status", code_type(16), nullable=False),
        sa.Column("overall_relative_score", mssql.DECIMAL(9, 6, asdecimal=True), nullable=False),
        sa.Column("source_rank", sa.SmallInteger(), nullable=False),
        sa.Column("label_value", code_type(16), nullable=False),
        sa.Column("source_path_revision_digest", code_type(64), nullable=False),
        sa.Column("source_outcome_latest_input_available_at", timestamp_type(), nullable=False),
        sa.Column("source_outcome_recorded_at", timestamp_type(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "probability_calibration_dataset_item_id",
            name="pk_probability_calibration_dataset_items",
        ),
        sa.ForeignKeyConstraint(
            ["probability_calibration_dataset_id"],
            ["trading.probability_calibration_datasets.probability_calibration_dataset_id"],
            name="fk_probability_calibration_dataset_items_dataset_datasets",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_outcome_label_id"],
            ["trading.daily_feature_outcome_labels.daily_feature_outcome_label_id"],
            name="fk_probability_calibration_dataset_items_label_labels",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_outcome_id"],
            ["trading.daily_feature_outcomes.daily_feature_outcome_id"],
            name="fk_probability_calibration_dataset_items_outcome_outcomes",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_run_id"],
            ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
            name="fk_probability_calibration_dataset_items_scoring_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_item_id"],
            ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
            name="fk_probability_calibration_dataset_items_scoring_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_run_id"],
            ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
            name="fk_probability_calibration_dataset_items_pipeline_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_item_id"],
            ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
            name="fk_probability_calibration_dataset_items_pipeline_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["trading.feature_snapshots.feature_snapshot_id"],
            name="fk_probability_calibration_dataset_items_snapshot_snapshots",
            ondelete="NO ACTION",
        ),
        _check("ordinal >= 1", "ordinal"),
        _check(symbol_check(), "symbol"),
        _check("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", "mic"),
        _check("horizon_trading_days BETWEEN 1 AND 5", "horizon"),
        _check("source_session_date < terminal_session_date", "session_order"),
        _check("observation_mode IN ('PROSPECTIVE','RETROSPECTIVE_REPLAY')", "mode"),
        _check("source_quality_status = 'READY'", "quality"),
        _check("overall_relative_score BETWEEN 0 AND 100", "score"),
        _check("source_rank BETWEEN 1 AND 100", "rank"),
        _check("label_value IN ('POSITIVE','NOT_POSITIVE')", "label"),
        _check(
            "source_outcome_latest_input_available_at <= generated_at "
            "AND source_outcome_recorded_at <= generated_at "
            "AND generated_at <= recorded_at",
            "time_order",
        ),
        _check(
            "DATALENGTH(source_outcome_key) = 89 "
            "AND source_outcome_key LIKE 'daily-feature-outcome:v1:%' "
            "AND RIGHT(source_outcome_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "outcome_key_format",
        ),
        _check(
            "DATALENGTH(source_outcome_content_digest) = 64 "
            "AND source_outcome_content_digest COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "source_outcome_content_digest_format",
        ),
        _check(
            "DATALENGTH(source_path_revision_digest) = 64 "
            "AND source_path_revision_digest COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "source_path_revision_digest_format",
        ),
        sa.UniqueConstraint(
            "probability_calibration_dataset_id",
            "ordinal",
            name="uq_probability_calibration_dataset_items_dataset_ordinal",
        ),
        sa.UniqueConstraint(
            "probability_calibration_dataset_id",
            "source_daily_feature_scoring_item_id",
            name="uq_probability_calibration_dataset_items_dataset_scoring_item",
        ),
        sa.UniqueConstraint(
            "probability_calibration_dataset_id",
            "source_daily_feature_outcome_id",
            name="uq_probability_calibration_dataset_items_dataset_outcome",
        ),
        sa.UniqueConstraint(
            "probability_calibration_dataset_id",
            "source_daily_feature_outcome_label_id",
            name="uq_probability_calibration_dataset_items_dataset_label",
        ),
        schema=SCHEMA,
    )
    indexes = (
        (
            "ix_probability_calibration_dataset_items_dataset_ordinal",
            ["probability_calibration_dataset_id", "ordinal"],
        ),
        ("ix_probability_calibration_dataset_items_source_session", ["source_session_date"]),
        (
            "ix_probability_calibration_dataset_items_mode_session",
            ["observation_mode", "source_session_date"],
        ),
        (
            "ix_probability_calibration_dataset_items_label_session",
            ["label_value", "source_session_date"],
        ),
        ("ix_probability_calibration_dataset_items_overall_score", ["overall_relative_score"]),
        (
            "ix_probability_calibration_dataset_items_source_scoring_item",
            ["source_daily_feature_scoring_item_id"],
        ),
        (
            "ix_probability_calibration_dataset_items_source_outcome",
            ["source_daily_feature_outcome_id"],
        ),
    )
    for name, columns in indexes:
        op.create_index(name, TABLE, columns, schema=SCHEMA)
