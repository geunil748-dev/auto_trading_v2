"""Canonical immutable P4B.1 outcome and observation audit tables."""

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
    decimal_type,
    json_array_check_sql,
    json_text_type,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

daily_feature_outcomes = Table(
    "daily_feature_outcomes",
    metadata,
    Column("daily_feature_outcome_id", uuid_type(), primary_key=True),
    Column("outcome_key", code_type(89), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("path_revision_digest", code_type(64), nullable=False),
    Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
    Column("feature_snapshot_id", uuid_type(), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("mic_code", code_type(4), nullable=False),
    Column("provider_code", code_type(64), nullable=False),
    Column("calendar_code", code_type(64), nullable=False),
    Column("calendar_version", code_type(64), nullable=False),
    Column("source_session_date", Date(), nullable=False),
    Column("terminal_session_date", Date(), nullable=False),
    Column("horizon_trading_days", SmallInteger(), nullable=False),
    Column("outcome_policy_code", code_type(64), nullable=False),
    Column("outcome_policy_version", code_type(64), nullable=False),
    Column("observation_as_of", timestamp_type(), nullable=False),
    Column("reference_close", decimal_type(), nullable=False),
    Column("terminal_close", decimal_type(), nullable=False),
    Column("forward_close_return", decimal_type(), nullable=False),
    Column("maximum_favorable_excursion_rate", decimal_type(), nullable=False),
    Column("maximum_adverse_excursion_rate", decimal_type(), nullable=False),
    Column("future_bar_count", SmallInteger(), nullable=False),
    Column("future_bar_provenance", json_text_type(), nullable=False),
    Column("latest_input_available_at", timestamp_type(), nullable=False),
    Column("observation_mode", code_type(32), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_run_id"],
        ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
        name="fk_daily_feature_outcomes_source_scoring_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_item_id"],
        ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
        name="fk_daily_feature_outcomes_source_scoring_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_run_id"],
        ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
        name="fk_daily_feature_outcomes_source_pipeline_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_item_id"],
        ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
        name="fk_daily_feature_outcomes_source_pipeline_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["feature_snapshot_id"],
        ["trading.feature_snapshots.feature_snapshot_id"],
        name="fk_daily_feature_outcomes_feature_snapshot_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", name="mic"),
    CheckConstraint("provider_code = 'TWELVE_DATA_TIME_SERIES'", name="provider"),
    CheckConstraint(
        "calendar_code = 'US_EQUITY_CORE' AND calendar_version = '2026.v1'",
        name="calendar",
    ),
    CheckConstraint(
        "outcome_policy_code = 'US_EQUITY_FORWARD_PATH_OBSERVATION' "
        "AND outcome_policy_version = 'v1'",
        name="policy",
    ),
    CheckConstraint("source_session_date < terminal_session_date", name="session_order"),
    CheckConstraint("horizon_trading_days BETWEEN 1 AND 5", name="horizon"),
    CheckConstraint("future_bar_count = horizon_trading_days", name="bar_count"),
    CheckConstraint("reference_close > 0 AND terminal_close > 0", name="prices"),
    CheckConstraint(
        "maximum_adverse_excursion_rate <= forward_close_return "
        "AND forward_close_return <= maximum_favorable_excursion_rate",
        name="rate_order",
    ),
    CheckConstraint(json_array_check_sql("future_bar_provenance"), name="provenance_json"),
    CheckConstraint(
        "latest_input_available_at <= observation_as_of "
        "AND observation_as_of <= generated_at AND generated_at <= recorded_at",
        name="time_order",
    ),
    CheckConstraint(
        "observation_mode IN ('PROSPECTIVE','RETROSPECTIVE_REPLAY')",
        name="mode",
    ),
    CheckConstraint(
        "DATALENGTH(outcome_key) = 89 AND outcome_key LIKE 'daily-feature-outcome:v1:%' "
        "AND RIGHT(outcome_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="outcome_key_format",
    ),
    *(
        CheckConstraint(
            f"DATALENGTH({name}) = 64 AND {name} COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            name=f"{name}_format",
        )
        for name in ("content_digest", "path_revision_digest")
    ),
    UniqueConstraint("outcome_key", name="uq_daily_feature_outcomes_key"),
    UniqueConstraint(
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
        ("source_daily_feature_scoring_item_id", "latest_input_available_at"),
    ),
    ("ix_daily_feature_outcomes_source_run", ("source_daily_feature_scoring_run_id",)),
    ("ix_daily_feature_outcomes_symbol_terminal", ("symbol", "terminal_session_date")),
    (
        "ix_daily_feature_outcomes_mode_terminal",
        ("observation_mode", "terminal_session_date"),
    ),
    ("ix_daily_feature_outcomes_snapshot", ("feature_snapshot_id",)),
    (
        "ix_daily_feature_outcomes_provider_terminal",
        ("provider_code", "terminal_session_date"),
    ),
):
    Index(name, *(daily_feature_outcomes.c[column] for column in columns))
