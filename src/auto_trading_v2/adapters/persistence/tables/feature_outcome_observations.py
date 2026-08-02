"""Immutable P4B.1 observation-run and run-item audit tables."""

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
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

daily_feature_outcome_observation_runs = Table(
    "daily_feature_outcome_observation_runs",
    metadata,
    Column("daily_feature_outcome_observation_run_id", uuid_type(), primary_key=True),
    Column("observation_run_key", code_type(93), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
    Column("outcome_policy_code", code_type(64), nullable=False),
    Column("outcome_policy_version", code_type(64), nullable=False),
    Column("observation_as_of", timestamp_type(), nullable=False),
    Column("completion_grace_seconds", Integer(), nullable=False),
    Column("status", code_type(32), nullable=False),
    Column("total_count", SmallInteger(), nullable=False),
    Column("outcome_created_count", SmallInteger(), nullable=False),
    Column("outcome_existing_count", SmallInteger(), nullable=False),
    Column("not_matured_count", SmallInteger(), nullable=False),
    Column("incomplete_count", SmallInteger(), nullable=False),
    Column("ineligible_count", SmallInteger(), nullable=False),
    Column("invalid_count", SmallInteger(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_run_id"],
        ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
        name="fk_outcome_observation_runs_source_scoring_run_runs",
        ondelete="NO ACTION",
    ),
    CheckConstraint(
        "outcome_policy_code = 'US_EQUITY_FORWARD_PATH_OBSERVATION' "
        "AND outcome_policy_version = 'v1'",
        name="policy",
    ),
    CheckConstraint("completion_grace_seconds BETWEEN 0 AND 86400", name="grace"),
    CheckConstraint(
        "status IN ('COMPLETED','COMPLETED_WITH_PENDING','COMPLETED_WITH_GAPS',"
        "'NO_ELIGIBLE_ITEMS','CALENDAR_OUT_OF_COVERAGE')",
        name="status",
    ),
    CheckConstraint(
        "total_count BETWEEN 0 AND 100 AND outcome_created_count BETWEEN 0 AND 100 "
        "AND outcome_existing_count BETWEEN 0 AND 100 "
        "AND not_matured_count BETWEEN 0 AND 100 "
        "AND incomplete_count BETWEEN 0 AND 100 AND ineligible_count BETWEEN 0 AND 100 "
        "AND invalid_count BETWEEN 0 AND 100",
        name="counts",
    ),
    CheckConstraint(
        "total_count = outcome_created_count + outcome_existing_count + not_matured_count "
        "+ incomplete_count + ineligible_count + invalid_count",
        name="count_sum",
    ),
    CheckConstraint(
        "(status = 'COMPLETED' AND not_matured_count = 0 AND incomplete_count = 0 "
        "AND invalid_count = 0) OR "
        "(status = 'COMPLETED_WITH_PENDING' "
        "AND not_matured_count + incomplete_count > 0 AND invalid_count = 0) OR "
        "(status = 'COMPLETED_WITH_GAPS' AND invalid_count > 0) OR "
        "(status = 'NO_ELIGIBLE_ITEMS' AND total_count = ineligible_count) OR "
        "(status = 'CALENDAR_OUT_OF_COVERAGE' AND invalid_count > 0)",
        name="status_shape",
    ),
    CheckConstraint("generated_at <= recorded_at", name="time_order"),
    CheckConstraint(
        "DATALENGTH(observation_run_key) = 93 "
        "AND observation_run_key LIKE 'daily-feature-outcome-run:v1:%' "
        "AND RIGHT(observation_run_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="run_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 AND content_digest "
        "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("observation_run_key", name="uq_outcome_observation_runs_key"),
    schema=SCHEMA,
)

daily_feature_outcome_observation_run_items = Table(
    "daily_feature_outcome_observation_run_items",
    metadata,
    Column("daily_feature_outcome_observation_run_item_id", uuid_type(), primary_key=True),
    Column("daily_feature_outcome_observation_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
    Column("ordinal", SmallInteger(), nullable=False),
    Column("outcome", code_type(32), nullable=False),
    Column("daily_feature_outcome_id", uuid_type(), nullable=True),
    Column("terminal_session_date", Date(), nullable=True),
    Column("safe_reason_code", code_type(96), nullable=True),
    Column("generated_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    ForeignKeyConstraint(
        ["daily_feature_outcome_observation_run_id"],
        ["trading.daily_feature_outcome_observation_runs.daily_feature_outcome_observation_run_id"],
        name="fk_outcome_observation_run_items_run_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_scoring_item_id"],
        ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
        name="fk_outcome_observation_run_items_source_scoring_item_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["daily_feature_outcome_id"],
        ["trading.daily_feature_outcomes.daily_feature_outcome_id"],
        name="fk_outcome_observation_run_items_outcome_outcomes",
        ondelete="NO ACTION",
    ),
    CheckConstraint("ordinal BETWEEN 1 AND 100", name="ordinal"),
    CheckConstraint(
        "outcome IN ('OUTCOME_CREATED','OUTCOME_ALREADY_EXISTS','NOT_MATURED',"
        "'FUTURE_BARS_INCOMPLETE','SOURCE_ITEM_NOT_ELIGIBLE','SOURCE_CHAIN_INVALID',"
        "'FUTURE_BAR_CONTRACT_INVALID','CALENDAR_OUT_OF_COVERAGE')",
        name="outcome",
    ),
    CheckConstraint(
        "(outcome IN ('OUTCOME_CREATED','OUTCOME_ALREADY_EXISTS') "
        "AND daily_feature_outcome_id IS NOT NULL AND terminal_session_date IS NOT NULL "
        "AND safe_reason_code IS NULL) OR (outcome NOT IN "
        "('OUTCOME_CREATED','OUTCOME_ALREADY_EXISTS') AND daily_feature_outcome_id IS NULL "
        "AND safe_reason_code IS NOT NULL)",
        name="outcome_shape",
    ),
    CheckConstraint("generated_at <= recorded_at", name="time_order"),
    UniqueConstraint(
        "daily_feature_outcome_observation_run_id",
        "ordinal",
        name="uq_outcome_observation_run_items_run_ordinal",
    ),
    UniqueConstraint(
        "daily_feature_outcome_observation_run_id",
        "source_daily_feature_scoring_item_id",
        name="uq_outcome_observation_run_items_run_source_item",
    ),
    schema=SCHEMA,
)

for name, table, columns in (
    (
        "ix_outcome_observation_runs_source",
        daily_feature_outcome_observation_runs,
        ("source_daily_feature_scoring_run_id",),
    ),
    (
        "ix_outcome_observation_runs_status_generated",
        daily_feature_outcome_observation_runs,
        ("status", "generated_at"),
    ),
    (
        "ix_outcome_observation_runs_as_of",
        daily_feature_outcome_observation_runs,
        ("observation_as_of",),
    ),
    (
        "ix_outcome_observation_items_run_ordinal",
        daily_feature_outcome_observation_run_items,
        ("daily_feature_outcome_observation_run_id", "ordinal"),
    ),
    (
        "ix_outcome_observation_items_outcome",
        daily_feature_outcome_observation_run_items,
        ("outcome",),
    ),
    (
        "ix_outcome_observation_items_source",
        daily_feature_outcome_observation_run_items,
        ("source_daily_feature_scoring_item_id",),
    ),
    (
        "ix_outcome_observation_items_outcome_id",
        daily_feature_outcome_observation_run_items,
        ("daily_feature_outcome_id",),
    ),
):
    Index(name, *(table.c[column] for column in columns))
