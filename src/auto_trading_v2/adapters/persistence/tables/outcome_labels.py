"""Canonical immutable P4B.2A positive-close labels."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKeyConstraint,
    Index,
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

daily_feature_outcome_labels = Table(
    "daily_feature_outcome_labels",
    metadata,
    Column("daily_feature_outcome_label_id", uuid_type(), primary_key=True),
    Column("label_key", code_type(95), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("source_daily_feature_outcome_id", uuid_type(), nullable=False),
    Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
    Column("feature_snapshot_id", uuid_type(), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("mic_code", code_type(4), nullable=False),
    Column("horizon_trading_days", SmallInteger(), nullable=False),
    Column("source_session_date", Date(), nullable=False),
    Column("terminal_session_date", Date(), nullable=False),
    Column("observation_mode", code_type(32), nullable=False),
    Column("source_path_revision_digest", code_type(64), nullable=False),
    Column("label_policy_code", code_type(64), nullable=False),
    Column("label_policy_version", code_type(64), nullable=False),
    Column("label_value", code_type(16), nullable=False),
    Column("source_latest_input_available_at", timestamp_type(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["source_daily_feature_outcome_id"],
        ["trading.daily_feature_outcomes.daily_feature_outcome_id"],
        name="fk_daily_feature_outcome_labels_source_outcome_outcomes",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_run_id"],
        ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
        name="fk_daily_feature_outcome_labels_source_scoring_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_item_id"],
        ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
        name="fk_daily_feature_outcome_labels_source_scoring_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_run_id"],
        ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
        name="fk_daily_feature_outcome_labels_source_pipeline_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_item_id"],
        ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
        name="fk_daily_feature_outcome_labels_source_pipeline_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["feature_snapshot_id"],
        ["trading.feature_snapshots.feature_snapshot_id"],
        name="fk_daily_feature_outcome_labels_snapshot_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", name="mic"),
    CheckConstraint("horizon_trading_days BETWEEN 1 AND 5", name="horizon"),
    CheckConstraint("source_session_date < terminal_session_date", name="session_order"),
    CheckConstraint("observation_mode IN ('PROSPECTIVE','RETROSPECTIVE_REPLAY')", name="mode"),
    CheckConstraint(
        "label_policy_code = 'US_EQUITY_POSITIVE_FORWARD_CLOSE_LABEL' "
        "AND label_policy_version = 'v1'",
        name="policy",
    ),
    CheckConstraint("label_value IN ('POSITIVE','NOT_POSITIVE')", name="value"),
    CheckConstraint(
        "source_latest_input_available_at <= generated_at AND generated_at <= recorded_at",
        name="time_order",
    ),
    CheckConstraint(
        "DATALENGTH(label_key) = 95 AND label_key LIKE 'daily-feature-outcome-label:v1:%' "
        "AND RIGHT(label_key, 64) COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="label_key_format",
    ),
    *(
        CheckConstraint(
            f"DATALENGTH({name}) = 64 AND {name} COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            name=f"{name}_format",
        )
        for name in ("content_digest", "source_path_revision_digest")
    ),
    UniqueConstraint("label_key", name="uq_daily_feature_outcome_labels_key"),
    UniqueConstraint(
        "source_daily_feature_outcome_id",
        "label_policy_code",
        "label_policy_version",
        name="uq_daily_feature_outcome_labels_source_policy",
    ),
    schema=SCHEMA,
)

for name, columns in (
    ("ix_daily_feature_outcome_labels_source_outcome", ("source_daily_feature_outcome_id",)),
    (
        "ix_daily_feature_outcome_labels_source_item_generated",
        ("source_daily_feature_scoring_item_id", "generated_at"),
    ),
    ("ix_daily_feature_outcome_labels_value_terminal", ("label_value", "terminal_session_date")),
    (
        "ix_daily_feature_outcome_labels_mode_terminal",
        ("observation_mode", "terminal_session_date"),
    ),
):
    Index(name, *(daily_feature_outcome_labels.c[column] for column in columns))
