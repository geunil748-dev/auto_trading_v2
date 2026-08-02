"""Canonical immutable P4B.2A dataset items."""

from sqlalchemy import (
    DECIMAL,
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
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

probability_calibration_dataset_items = Table(
    "probability_calibration_dataset_items",
    metadata,
    Column("probability_calibration_dataset_item_id", uuid_type(), primary_key=True),
    Column("probability_calibration_dataset_id", uuid_type(), nullable=False),
    Column("ordinal", Integer(), nullable=False),
    Column("source_daily_feature_outcome_label_id", uuid_type(), nullable=False),
    Column("source_daily_feature_outcome_id", uuid_type(), nullable=False),
    Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
    Column("feature_snapshot_id", uuid_type(), nullable=False),
    Column("source_outcome_key", code_type(89), nullable=False),
    Column("source_outcome_content_digest", code_type(64), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("mic_code", code_type(4), nullable=False),
    Column("horizon_trading_days", SmallInteger(), nullable=False),
    Column("source_session_date", Date(), nullable=False),
    Column("terminal_session_date", Date(), nullable=False),
    Column("observation_mode", code_type(32), nullable=False),
    Column("source_quality_status", code_type(16), nullable=False),
    Column("overall_relative_score", DECIMAL(9, 6, asdecimal=True), nullable=False),
    Column("source_rank", SmallInteger(), nullable=False),
    Column("label_value", code_type(16), nullable=False),
    Column("source_path_revision_digest", code_type(64), nullable=False),
    Column("source_outcome_latest_input_available_at", timestamp_type(), nullable=False),
    Column("source_outcome_recorded_at", timestamp_type(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["probability_calibration_dataset_id"],
        ["trading.probability_calibration_datasets.probability_calibration_dataset_id"],
        name="fk_probability_calibration_dataset_items_dataset_datasets",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_outcome_label_id"],
        ["trading.daily_feature_outcome_labels.daily_feature_outcome_label_id"],
        name="fk_probability_calibration_dataset_items_label_labels",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_outcome_id"],
        ["trading.daily_feature_outcomes.daily_feature_outcome_id"],
        name="fk_probability_calibration_dataset_items_outcome_outcomes",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_run_id"],
        ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
        name="fk_probability_calibration_dataset_items_scoring_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_item_id"],
        ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
        name="fk_probability_calibration_dataset_items_scoring_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_run_id"],
        ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
        name="fk_probability_calibration_dataset_items_pipeline_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_item_id"],
        ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
        name="fk_probability_calibration_dataset_items_pipeline_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["feature_snapshot_id"],
        ["trading.feature_snapshots.feature_snapshot_id"],
        name="fk_probability_calibration_dataset_items_snapshot_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint("ordinal >= 1", name="ordinal"),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", name="mic"),
    CheckConstraint("horizon_trading_days BETWEEN 1 AND 5", name="horizon"),
    CheckConstraint("source_session_date < terminal_session_date", name="session_order"),
    CheckConstraint("observation_mode IN ('PROSPECTIVE','RETROSPECTIVE_REPLAY')", name="mode"),
    CheckConstraint("source_quality_status = 'READY'", name="quality"),
    CheckConstraint("overall_relative_score BETWEEN 0 AND 100", name="score"),
    CheckConstraint("source_rank BETWEEN 1 AND 100", name="rank"),
    CheckConstraint("label_value IN ('POSITIVE','NOT_POSITIVE')", name="label"),
    CheckConstraint(
        "source_outcome_latest_input_available_at <= generated_at "
        "AND source_outcome_recorded_at <= generated_at "
        "AND generated_at <= recorded_at",
        name="time_order",
    ),
    CheckConstraint(
        "DATALENGTH(source_outcome_key) = 89 "
        "AND source_outcome_key LIKE 'daily-feature-outcome:v1:%' "
        "AND RIGHT(source_outcome_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="outcome_key_format",
    ),
    *(
        CheckConstraint(
            f"DATALENGTH({name}) = 64 "
            f"AND {name} COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            name=f"{name}_format",
        )
        for name in ("source_outcome_content_digest", "source_path_revision_digest")
    ),
    UniqueConstraint(
        "probability_calibration_dataset_id",
        "ordinal",
        name="uq_probability_calibration_dataset_items_dataset_ordinal",
    ),
    UniqueConstraint(
        "probability_calibration_dataset_id",
        "source_daily_feature_scoring_item_id",
        name="uq_probability_calibration_dataset_items_dataset_scoring_item",
    ),
    UniqueConstraint(
        "probability_calibration_dataset_id",
        "source_daily_feature_outcome_id",
        name="uq_probability_calibration_dataset_items_dataset_outcome",
    ),
    UniqueConstraint(
        "probability_calibration_dataset_id",
        "source_daily_feature_outcome_label_id",
        name="uq_probability_calibration_dataset_items_dataset_label",
    ),
    schema=SCHEMA,
)

for name, columns in (
    (
        "ix_probability_calibration_dataset_items_dataset_ordinal",
        ("probability_calibration_dataset_id", "ordinal"),
    ),
    ("ix_probability_calibration_dataset_items_source_session", ("source_session_date",)),
    (
        "ix_probability_calibration_dataset_items_mode_session",
        ("observation_mode", "source_session_date"),
    ),
    (
        "ix_probability_calibration_dataset_items_label_session",
        ("label_value", "source_session_date"),
    ),
    ("ix_probability_calibration_dataset_items_overall_score", ("overall_relative_score",)),
    (
        "ix_probability_calibration_dataset_items_source_scoring_item",
        ("source_daily_feature_scoring_item_id",),
    ),
    (
        "ix_probability_calibration_dataset_items_source_outcome",
        ("source_daily_feature_outcome_id",),
    ),
):
    Index(name, *(probability_calibration_dataset_items.c[column] for column in columns))
