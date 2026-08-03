"""Additive DDL for immutable P4B.1 observation-run audits."""

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

TABLE = "daily_feature_outcome_observation_runs"


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{TABLE}_{suffix}")


def create_daily_feature_outcome_observation_runs_table(op: Operations) -> None:
    op.create_table(
        "daily_feature_outcome_observation_runs",
        sa.Column("daily_feature_outcome_observation_run_id", uuid_type(), nullable=False),
        sa.Column("observation_run_key", code_type(93), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("source_daily_feature_scoring_run_id", uuid_type(), nullable=False),
        sa.Column("outcome_policy_code", code_type(64), nullable=False),
        sa.Column("outcome_policy_version", code_type(64), nullable=False),
        sa.Column("observation_as_of", timestamp_type(), nullable=False),
        sa.Column("completion_grace_seconds", sa.Integer(), nullable=False),
        sa.Column("status", code_type(32), nullable=False),
        sa.Column("total_count", sa.SmallInteger(), nullable=False),
        sa.Column("outcome_created_count", sa.SmallInteger(), nullable=False),
        sa.Column("outcome_existing_count", sa.SmallInteger(), nullable=False),
        sa.Column("not_matured_count", sa.SmallInteger(), nullable=False),
        sa.Column("incomplete_count", sa.SmallInteger(), nullable=False),
        sa.Column("ineligible_count", sa.SmallInteger(), nullable=False),
        sa.Column("invalid_count", sa.SmallInteger(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_outcome_observation_run_id",
            name="pk_daily_feature_outcome_observation_runs",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_run_id"],
            ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
            name="fk_outcome_observation_runs_source_scoring_run_runs",
            ondelete="NO ACTION",
        ),
        _check(
            "outcome_policy_code = 'US_EQUITY_FORWARD_PATH_OBSERVATION' "
            "AND outcome_policy_version = 'v1'",
            "policy",
        ),
        _check("completion_grace_seconds BETWEEN 0 AND 86400", "grace"),
        _check(
            "status IN ('COMPLETED','COMPLETED_WITH_PENDING','COMPLETED_WITH_GAPS',"
            "'NO_ELIGIBLE_ITEMS','CALENDAR_OUT_OF_COVERAGE')",
            "status",
        ),
        _check(
            "total_count BETWEEN 0 AND 100 AND outcome_created_count BETWEEN 0 AND 100 "
            "AND outcome_existing_count BETWEEN 0 AND 100 "
            "AND not_matured_count BETWEEN 0 AND 100 "
            "AND incomplete_count BETWEEN 0 AND 100 "
            "AND ineligible_count BETWEEN 0 AND 100 AND invalid_count BETWEEN 0 AND 100",
            "counts",
        ),
        _check(
            "total_count = outcome_created_count + outcome_existing_count "
            "+ not_matured_count + incomplete_count + ineligible_count + invalid_count",
            "count_sum",
        ),
        _check(
            "(status = 'COMPLETED' AND not_matured_count = 0 AND incomplete_count = 0 "
            "AND invalid_count = 0) OR "
            "(status = 'COMPLETED_WITH_PENDING' "
            "AND not_matured_count + incomplete_count > 0 AND invalid_count = 0) OR "
            "(status = 'COMPLETED_WITH_GAPS' AND invalid_count > 0) OR "
            "(status = 'NO_ELIGIBLE_ITEMS' AND total_count = ineligible_count) OR "
            "(status = 'CALENDAR_OUT_OF_COVERAGE' AND invalid_count > 0)",
            "status_shape",
        ),
        _check("generated_at <= recorded_at", "time_order"),
        _check(
            "DATALENGTH(observation_run_key) = 93 "
            "AND observation_run_key LIKE 'daily-feature-outcome-run:v1:%' "
            "AND RIGHT(observation_run_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "run_key_format",
        ),
        _check(
            "DATALENGTH(content_digest) = 64 AND content_digest "
            "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        sa.UniqueConstraint("observation_run_key", name="uq_outcome_observation_runs_key"),
        schema=SCHEMA,
    )
    for name, columns in (
        ("ix_outcome_observation_runs_source", ["source_daily_feature_scoring_run_id"]),
        ("ix_outcome_observation_runs_status_generated", ["status", "generated_at"]),
        ("ix_outcome_observation_runs_as_of", ["observation_as_of"]),
    ):
        op.create_index(name, TABLE, columns, schema=SCHEMA)
