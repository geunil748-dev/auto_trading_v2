"""Additive DDL for canonical immutable Recommendations."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    currency_type,
    decimal_type,
    json_array_check,
    json_type,
    named_check_constraint,
    timestamp_type,
    uuid_type,
)

_ACTIONABLE = "'RECOMMEND', 'CONDITIONAL'"
_NON_ACTIONABLE = "'WATCH', 'NO_RECOMMENDATION', 'DATA_INSUFFICIENT', 'MARKET_RISK'"
_PLAN_COLUMNS = (
    "currency",
    "entry_price_low",
    "entry_price_high",
    "target_price",
    "stop_price",
    "expected_holding_trading_days",
    "upside_probability",
    "target_probability",
    "stop_probability",
    "expected_value_rate",
    "reward_risk_ratio",
    "confidence",
    "valid_until",
)
_ALL_PLAN_PRESENT = " AND ".join(f"{column} IS NOT NULL" for column in _PLAN_COLUMNS)
_ALL_PLAN_NULL = " AND ".join(f"{column} IS NULL" for column in _PLAN_COLUMNS)


def _check(sql: str, name: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_recommendations_{name}")


def create_recommendations_table(op: Operations) -> None:
    """Create only trading.recommendations."""

    op.create_table(
        "recommendations",
        sa.Column("recommendation_id", uuid_type(), nullable=False),
        sa.Column("recommendation_key", code_type(82), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("feature_snapshot_id", uuid_type(), nullable=False),
        sa.Column("generator_code", code_type(64), nullable=False),
        sa.Column("generator_version", code_type(64), nullable=False),
        sa.Column("disposition", code_type(32), nullable=False),
        sa.Column("currency", currency_type(), nullable=True),
        sa.Column("entry_price_low", decimal_type(), nullable=True),
        sa.Column("entry_price_high", decimal_type(), nullable=True),
        sa.Column("target_price", decimal_type(), nullable=True),
        sa.Column("stop_price", decimal_type(), nullable=True),
        sa.Column("expected_holding_trading_days", sa.SmallInteger(), nullable=True),
        sa.Column("upside_probability", decimal_type(), nullable=True),
        sa.Column("target_probability", decimal_type(), nullable=True),
        sa.Column("stop_probability", decimal_type(), nullable=True),
        sa.Column("expected_value_rate", decimal_type(), nullable=True),
        sa.Column("reward_risk_ratio", decimal_type(), nullable=True),
        sa.Column("confidence", decimal_type(), nullable=True),
        sa.Column("valid_until", timestamp_type(), nullable=True),
        sa.Column("reason_codes", json_type(), nullable=False),
        sa.Column("risk_codes", json_type(), nullable=False),
        sa.Column("invalidation_codes", json_type(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("recommendation_id", name="pk_recommendations"),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["trading.feature_snapshots.feature_snapshot_id"],
            name="fk_recommendations_feature_snapshot_id_feature_snapshots",
            ondelete="NO ACTION",
        ),
        _check(
            "DATALENGTH(LTRIM(RTRIM(generator_code))) > 0",
            "generator_code_nonempty",
        ),
        _check(
            "DATALENGTH(LTRIM(RTRIM(generator_version))) > 0",
            "generator_version_nonempty",
        ),
        _check(
            "disposition IN "
            "('RECOMMEND', 'CONDITIONAL', 'WATCH', 'NO_RECOMMENDATION', "
            "'DATA_INSUFFICIENT', 'MARKET_RISK')",
            "disposition",
        ),
        _check(json_array_check("reason_codes"), "reason_codes_json_array"),
        _check(json_array_check("risk_codes"), "risk_codes_json_array"),
        _check(json_array_check("invalidation_codes"), "invalidation_codes_json_array"),
        _check("reason_codes <> '[]'", "reason_codes_nonempty"),
        _check(
            f"(disposition IN ({_ACTIONABLE}) AND {_ALL_PLAN_PRESENT}) OR "
            f"(disposition IN ({_NON_ACTIONABLE}) AND {_ALL_PLAN_NULL})",
            "plan_shape",
        ),
        _check("currency IS NULL OR currency = 'USD'", "currency_usd"),
        _check(
            "entry_price_low IS NULL OR "
            "(stop_price > 0 AND entry_price_low > 0 AND entry_price_high > 0 "
            "AND target_price > 0)",
            "prices_positive",
        ),
        _check(
            "entry_price_low IS NULL OR "
            "(stop_price < entry_price_low AND entry_price_low <= entry_price_high "
            "AND entry_price_high < target_price)",
            "price_order",
        ),
        _check(
            "expected_holding_trading_days IS NULL "
            "OR expected_holding_trading_days BETWEEN 1 AND 5",
            "holding_days",
        ),
        _check(
            "upside_probability IS NULL OR "
            "(upside_probability BETWEEN 0 AND 1 "
            "AND target_probability BETWEEN 0 AND 1 "
            "AND stop_probability BETWEEN 0 AND 1)",
            "probabilities",
        ),
        _check(
            "target_probability IS NULL OR target_probability + stop_probability <= 1",
            "target_stop_probability",
        ),
        _check(
            "expected_value_rate IS NULL OR expected_value_rate > 0",
            "expected_value_positive",
        ),
        _check(
            "reward_risk_ratio IS NULL OR reward_risk_ratio > 0",
            "reward_risk_positive",
        ),
        _check("confidence IS NULL OR confidence BETWEEN 0 AND 1", "confidence"),
        _check("valid_until IS NULL OR valid_until > generated_at", "valid_until"),
        _check(
            f"disposition NOT IN ({_ACTIONABLE}) OR risk_codes <> '[]'",
            "actionable_risk_nonempty",
        ),
        _check(
            f"disposition NOT IN ({_ACTIONABLE}) OR invalidation_codes <> '[]'",
            "actionable_invalidation_nonempty",
        ),
        _check(
            f"disposition NOT IN ({_NON_ACTIONABLE}) OR invalidation_codes = '[]'",
            "non_actionable_invalidation_empty",
        ),
        _check(
            "disposition <> 'MARKET_RISK' OR risk_codes <> '[]'",
            "market_risk_nonempty",
        ),
        _check(
            "DATALENGTH(recommendation_key) = 82 "
            "AND recommendation_key LIKE 'recommendation:v1:%' "
            "AND RIGHT(recommendation_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "recommendation_key_format",
        ),
        _check(
            "DATALENGTH(content_digest) = 64 "
            "AND content_digest COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        sa.UniqueConstraint(
            "recommendation_key",
            name="uq_recommendations_recommendation_key",
        ),
        sa.UniqueConstraint(
            "feature_snapshot_id",
            "generator_code",
            "generator_version",
            name="uq_recommendations_semantic_identity",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_recommendations_feature_snapshot_id",
        "recommendations",
        ["feature_snapshot_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_recommendations_disposition_generated_at",
        "recommendations",
        ["disposition", "generated_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_recommendations_generator_generated_at",
        "recommendations",
        ["generator_code", "generator_version", "generated_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_recommendations_generated_at",
        "recommendations",
        ["generated_at"],
        schema=SCHEMA,
    )
