"""Additive DDL for immutable P4B.2A dataset headers."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    named_check_constraint,
    timestamp_type,
    uuid_type,
)

TABLE = "probability_calibration_datasets"


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{TABLE}_{suffix}")


def create_probability_calibration_datasets_table(op: Operations) -> None:
    op.create_table(
        "probability_calibration_datasets",
        sa.Column("probability_calibration_dataset_id", uuid_type(), nullable=False),
        sa.Column("dataset_key", code_type(99), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("dataset_policy_code", code_type(64), nullable=False),
        sa.Column("dataset_policy_version", code_type(64), nullable=False),
        sa.Column("label_policy_code", code_type(64), nullable=False),
        sa.Column("label_policy_version", code_type(64), nullable=False),
        sa.Column("outcome_policy_code", code_type(64), nullable=False),
        sa.Column("outcome_policy_version", code_type(64), nullable=False),
        sa.Column("scoring_policy_code", code_type(64), nullable=False),
        sa.Column("scoring_policy_version", code_type(64), nullable=False),
        sa.Column("ranking_policy_code", code_type(64), nullable=False),
        sa.Column("ranking_policy_version", code_type(64), nullable=False),
        sa.Column("provider_code", code_type(64), nullable=False),
        sa.Column("calendar_code", code_type(64), nullable=False),
        sa.Column("calendar_version", code_type(64), nullable=False),
        sa.Column("horizon_trading_days", sa.SmallInteger(), nullable=False),
        sa.Column("dataset_as_of", timestamp_type(), nullable=False),
        sa.Column("status", code_type(16), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("positive_count", sa.Integer(), nullable=False),
        sa.Column("not_positive_count", sa.Integer(), nullable=False),
        sa.Column("prospective_count", sa.Integer(), nullable=False),
        sa.Column("retrospective_replay_count", sa.Integer(), nullable=False),
        sa.Column("unique_source_session_count", sa.Integer(), nullable=False),
        sa.Column("earliest_source_session_date", sa.Date(), nullable=True),
        sa.Column("latest_source_session_date", sa.Date(), nullable=True),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "probability_calibration_dataset_id", name="pk_probability_calibration_datasets"
        ),
        _check(
            "dataset_policy_code = 'READY_SCORE_POSITIVE_CLOSE_CALIBRATION_DATASET' "
            "AND dataset_policy_version = 'v1'",
            "dataset_policy",
        ),
        _check(
            "label_policy_code = 'US_EQUITY_POSITIVE_FORWARD_CLOSE_LABEL' "
            "AND label_policy_version = 'v1'",
            "label_policy",
        ),
        _check(
            "outcome_policy_code = 'US_EQUITY_FORWARD_PATH_OBSERVATION' "
            "AND outcome_policy_version = 'v1'",
            "outcome_policy",
        ),
        _check(
            "scoring_policy_code = 'US_EQUITY_DAILY_TECHNICAL_RELATIVE_SCORE' "
            "AND scoring_policy_version = 'v1'",
            "scoring_policy",
        ),
        _check(
            "ranking_policy_code = 'QUALITY_TIERED_CROSS_SECTIONAL_PERCENTILE' "
            "AND ranking_policy_version = 'v1'",
            "ranking_policy",
        ),
        _check("provider_code = 'TWELVE_DATA_TIME_SERIES'", "provider"),
        _check("calendar_code = 'US_EQUITY_CORE' AND calendar_version = '2026.v1'", "calendar"),
        _check("horizon_trading_days BETWEEN 1 AND 5", "horizon"),
        _check("status IN ('READY','EMPTY')", "status"),
        _check(
            "total_count >= 0 AND positive_count >= 0 AND not_positive_count >= 0 "
            "AND prospective_count >= 0 AND retrospective_replay_count >= 0 "
            "AND unique_source_session_count >= 0",
            "counts",
        ),
        _check("total_count = positive_count + not_positive_count", "label_count_sum"),
        _check("total_count = prospective_count + retrospective_replay_count", "mode_count_sum"),
        _check("dataset_as_of <= generated_at AND generated_at <= recorded_at", "time_order"),
        _check(
            "(status = 'EMPTY' AND total_count = 0 "
            "AND unique_source_session_count = 0 "
            "AND earliest_source_session_date IS NULL "
            "AND latest_source_session_date IS NULL) OR "
            "(status = 'READY' AND total_count > 0 "
            "AND unique_source_session_count > 0 "
            "AND earliest_source_session_date IS NOT NULL "
            "AND latest_source_session_date IS NOT NULL "
            "AND earliest_source_session_date <= latest_source_session_date)",
            "status_shape",
        ),
        _check(
            "DATALENGTH(dataset_key) = 99 "
            "AND dataset_key LIKE 'probability-calibration-dataset:v1:%' "
            "AND RIGHT(dataset_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "dataset_key_format",
        ),
        _check(
            "DATALENGTH(content_digest) = 64 "
            "AND content_digest COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        sa.UniqueConstraint("dataset_key", name="uq_probability_calibration_datasets_key"),
        schema=SCHEMA,
    )
    indexes = (
        (
            "ix_probability_calibration_datasets_horizon_as_of",
            ["horizon_trading_days", "dataset_as_of"],
        ),
        ("ix_probability_calibration_datasets_status_generated", ["status", "generated_at"]),
        (
            "ix_probability_calibration_datasets_policy_horizon_generated",
            [
                "dataset_policy_code",
                "dataset_policy_version",
                "horizon_trading_days",
                "generated_at",
            ],
        ),
    )
    for name, columns in indexes:
        op.create_index(name, TABLE, columns, schema=SCHEMA)
