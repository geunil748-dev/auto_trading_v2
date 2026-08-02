"""Canonical immutable P4B.2A dataset snapshot headers."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
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

probability_calibration_datasets = Table(
    "probability_calibration_datasets",
    metadata,
    Column("probability_calibration_dataset_id", uuid_type(), primary_key=True),
    Column("dataset_key", code_type(99), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("dataset_policy_code", code_type(64), nullable=False),
    Column("dataset_policy_version", code_type(64), nullable=False),
    Column("label_policy_code", code_type(64), nullable=False),
    Column("label_policy_version", code_type(64), nullable=False),
    Column("outcome_policy_code", code_type(64), nullable=False),
    Column("outcome_policy_version", code_type(64), nullable=False),
    Column("scoring_policy_code", code_type(64), nullable=False),
    Column("scoring_policy_version", code_type(64), nullable=False),
    Column("ranking_policy_code", code_type(64), nullable=False),
    Column("ranking_policy_version", code_type(64), nullable=False),
    Column("provider_code", code_type(64), nullable=False),
    Column("calendar_code", code_type(64), nullable=False),
    Column("calendar_version", code_type(64), nullable=False),
    Column("horizon_trading_days", SmallInteger(), nullable=False),
    Column("dataset_as_of", timestamp_type(), nullable=False),
    Column("status", code_type(16), nullable=False),
    Column("total_count", Integer(), nullable=False),
    Column("positive_count", Integer(), nullable=False),
    Column("not_positive_count", Integer(), nullable=False),
    Column("prospective_count", Integer(), nullable=False),
    Column("retrospective_replay_count", Integer(), nullable=False),
    Column("unique_source_session_count", Integer(), nullable=False),
    Column("earliest_source_session_date", Date(), nullable=True),
    Column("latest_source_session_date", Date(), nullable=True),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    CheckConstraint(
        "dataset_policy_code = 'READY_SCORE_POSITIVE_CLOSE_CALIBRATION_DATASET' "
        "AND dataset_policy_version = 'v1'",
        name="dataset_policy",
    ),
    CheckConstraint(
        "label_policy_code = 'US_EQUITY_POSITIVE_FORWARD_CLOSE_LABEL' "
        "AND label_policy_version = 'v1'",
        name="label_policy",
    ),
    CheckConstraint(
        "outcome_policy_code = 'US_EQUITY_FORWARD_PATH_OBSERVATION' "
        "AND outcome_policy_version = 'v1'",
        name="outcome_policy",
    ),
    CheckConstraint(
        "scoring_policy_code = 'US_EQUITY_DAILY_TECHNICAL_RELATIVE_SCORE' "
        "AND scoring_policy_version = 'v1'",
        name="scoring_policy",
    ),
    CheckConstraint(
        "ranking_policy_code = 'QUALITY_TIERED_CROSS_SECTIONAL_PERCENTILE' "
        "AND ranking_policy_version = 'v1'",
        name="ranking_policy",
    ),
    CheckConstraint("provider_code = 'TWELVE_DATA_TIME_SERIES'", name="provider"),
    CheckConstraint(
        "calendar_code = 'US_EQUITY_CORE' AND calendar_version = '2026.v1'", name="calendar"
    ),
    CheckConstraint("horizon_trading_days BETWEEN 1 AND 5", name="horizon"),
    CheckConstraint("status IN ('READY','EMPTY')", name="status"),
    CheckConstraint(
        "total_count >= 0 AND positive_count >= 0 AND not_positive_count >= 0 "
        "AND prospective_count >= 0 AND retrospective_replay_count >= 0 "
        "AND unique_source_session_count >= 0",
        name="counts",
    ),
    CheckConstraint("total_count = positive_count + not_positive_count", name="label_count_sum"),
    CheckConstraint(
        "total_count = prospective_count + retrospective_replay_count", name="mode_count_sum"
    ),
    CheckConstraint(
        "dataset_as_of <= generated_at AND generated_at <= recorded_at", name="time_order"
    ),
    CheckConstraint(
        "(status = 'EMPTY' AND total_count = 0 "
        "AND unique_source_session_count = 0 "
        "AND earliest_source_session_date IS NULL "
        "AND latest_source_session_date IS NULL) OR "
        "(status = 'READY' AND total_count > 0 "
        "AND unique_source_session_count > 0 "
        "AND earliest_source_session_date IS NOT NULL "
        "AND latest_source_session_date IS NOT NULL "
        "AND earliest_source_session_date <= latest_source_session_date)",
        name="status_shape",
    ),
    CheckConstraint(
        "DATALENGTH(dataset_key) = 99 "
        "AND dataset_key LIKE 'probability-calibration-dataset:v1:%' "
        "AND RIGHT(dataset_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="dataset_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 "
        "AND content_digest COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("dataset_key", name="uq_probability_calibration_datasets_key"),
    schema=SCHEMA,
)

Index(
    "ix_probability_calibration_datasets_horizon_as_of",
    probability_calibration_datasets.c.horizon_trading_days,
    probability_calibration_datasets.c.dataset_as_of,
)
Index(
    "ix_probability_calibration_datasets_status_generated",
    probability_calibration_datasets.c.status,
    probability_calibration_datasets.c.generated_at,
)
Index(
    "ix_probability_calibration_datasets_policy_horizon_generated",
    probability_calibration_datasets.c.dataset_policy_code,
    probability_calibration_datasets.c.dataset_policy_version,
    probability_calibration_datasets.c.horizon_trading_days,
    probability_calibration_datasets.c.generated_at,
)
