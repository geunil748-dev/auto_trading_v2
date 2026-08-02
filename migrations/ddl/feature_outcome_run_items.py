"""Additive DDL for immutable P4B.1 observation run-item audits."""

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

TABLE = "daily_feature_outcome_observation_run_items"


def _check(sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{TABLE}_{suffix}")


def create_daily_feature_outcome_observation_run_items_table(op: Operations) -> None:
    op.create_table(
        "daily_feature_outcome_observation_run_items",
        sa.Column("daily_feature_outcome_observation_run_item_id", uuid_type(), nullable=False),
        sa.Column("daily_feature_outcome_observation_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_scoring_item_id", uuid_type(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("outcome", code_type(32), nullable=False),
        sa.Column("daily_feature_outcome_id", uuid_type(), nullable=True),
        sa.Column("terminal_session_date", sa.Date(), nullable=True),
        sa.Column("safe_reason_code", code_type(96), nullable=True),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_outcome_observation_run_item_id",
            name="pk_daily_feature_outcome_observation_run_items",
        ),
        sa.ForeignKeyConstraint(
            ["daily_feature_outcome_observation_run_id"],
            [
                "trading.daily_feature_outcome_observation_runs.daily_feature_outcome_observation_run_id"
            ],
            name="fk_outcome_observation_run_items_run_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_scoring_item_id"],
            ["trading.daily_feature_scoring_items.daily_feature_scoring_item_id"],
            name="fk_outcome_observation_run_items_source_scoring_item_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["daily_feature_outcome_id"],
            ["trading.daily_feature_outcomes.daily_feature_outcome_id"],
            name="fk_outcome_observation_run_items_outcome_outcomes",
            ondelete="NO ACTION",
        ),
        _check("ordinal BETWEEN 1 AND 100", "ordinal"),
        _check(
            "outcome IN ('OUTCOME_CREATED','OUTCOME_ALREADY_EXISTS','NOT_MATURED',"
            "'FUTURE_BARS_INCOMPLETE','SOURCE_ITEM_NOT_ELIGIBLE','SOURCE_CHAIN_INVALID',"
            "'FUTURE_BAR_CONTRACT_INVALID','CALENDAR_OUT_OF_COVERAGE')",
            "outcome",
        ),
        _check(
            "(outcome IN ('OUTCOME_CREATED','OUTCOME_ALREADY_EXISTS') "
            "AND daily_feature_outcome_id IS NOT NULL AND terminal_session_date IS NOT NULL "
            "AND safe_reason_code IS NULL) OR (outcome NOT IN "
            "('OUTCOME_CREATED','OUTCOME_ALREADY_EXISTS') "
            "AND daily_feature_outcome_id IS NULL AND safe_reason_code IS NOT NULL)",
            "outcome_shape",
        ),
        _check("generated_at <= recorded_at", "time_order"),
        sa.UniqueConstraint(
            "daily_feature_outcome_observation_run_id",
            "ordinal",
            name="uq_outcome_observation_run_items_run_ordinal",
        ),
        sa.UniqueConstraint(
            "daily_feature_outcome_observation_run_id",
            "source_daily_feature_scoring_item_id",
            name="uq_outcome_observation_run_items_run_source_item",
        ),
        schema=SCHEMA,
    )
    for name, columns in (
        (
            "ix_outcome_observation_items_run_ordinal",
            ["daily_feature_outcome_observation_run_id", "ordinal"],
        ),
        ("ix_outcome_observation_items_outcome", ["outcome"]),
        ("ix_outcome_observation_items_source", ["source_daily_feature_scoring_item_id"]),
        ("ix_outcome_observation_items_outcome_id", ["daily_feature_outcome_id"]),
    ):
        op.create_index(name, TABLE, columns, schema=SCHEMA)
