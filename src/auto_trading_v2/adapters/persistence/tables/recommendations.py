"""Canonical immutable Recommendation table."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Table,
    UniqueConstraint,
)

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    currency_type,
    decimal_type,
    json_array_check_sql,
    json_text_type,
    non_empty_check_sql,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"
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

recommendations = Table(
    "recommendations",
    metadata,
    Column("recommendation_id", uuid_type(), primary_key=True),
    Column("recommendation_key", code_type(82), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("feature_snapshot_id", uuid_type(), nullable=False),
    Column("generator_code", code_type(64), nullable=False),
    Column("generator_version", code_type(64), nullable=False),
    Column("disposition", code_type(32), nullable=False),
    Column("currency", currency_type(), nullable=True),
    Column("entry_price_low", decimal_type(), nullable=True),
    Column("entry_price_high", decimal_type(), nullable=True),
    Column("target_price", decimal_type(), nullable=True),
    Column("stop_price", decimal_type(), nullable=True),
    Column("expected_holding_trading_days", SmallInteger(), nullable=True),
    Column("upside_probability", decimal_type(), nullable=True),
    Column("target_probability", decimal_type(), nullable=True),
    Column("stop_probability", decimal_type(), nullable=True),
    Column("expected_value_rate", decimal_type(), nullable=True),
    Column("reward_risk_ratio", decimal_type(), nullable=True),
    Column("confidence", decimal_type(), nullable=True),
    Column("valid_until", timestamp_type(), nullable=True),
    Column("reason_codes", json_text_type(), nullable=False),
    Column("risk_codes", json_text_type(), nullable=False),
    Column("invalidation_codes", json_text_type(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    ForeignKeyConstraint(
        ["feature_snapshot_id"],
        ["trading.feature_snapshots.feature_snapshot_id"],
        name="fk_recommendations_feature_snapshot_id_feature_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint(non_empty_check_sql("generator_code"), name="generator_code_nonempty"),
    CheckConstraint(
        non_empty_check_sql("generator_version"),
        name="generator_version_nonempty",
    ),
    CheckConstraint(
        "disposition IN "
        "('RECOMMEND', 'CONDITIONAL', 'WATCH', 'NO_RECOMMENDATION', "
        "'DATA_INSUFFICIENT', 'MARKET_RISK')",
        name="disposition",
    ),
    CheckConstraint(json_array_check_sql("reason_codes"), name="reason_codes_json_array"),
    CheckConstraint(json_array_check_sql("risk_codes"), name="risk_codes_json_array"),
    CheckConstraint(
        json_array_check_sql("invalidation_codes"),
        name="invalidation_codes_json_array",
    ),
    CheckConstraint("reason_codes <> '[]'", name="reason_codes_nonempty"),
    CheckConstraint(
        f"(disposition IN ({_ACTIONABLE}) AND {_ALL_PLAN_PRESENT}) OR "
        f"(disposition IN ({_NON_ACTIONABLE}) AND {_ALL_PLAN_NULL})",
        name="plan_shape",
    ),
    CheckConstraint("currency IS NULL OR currency = 'USD'", name="currency_usd"),
    CheckConstraint(
        "entry_price_low IS NULL OR "
        "(stop_price > 0 AND entry_price_low > 0 AND entry_price_high > 0 "
        "AND target_price > 0)",
        name="prices_positive",
    ),
    CheckConstraint(
        "entry_price_low IS NULL OR "
        "(stop_price < entry_price_low AND entry_price_low <= entry_price_high "
        "AND entry_price_high < target_price)",
        name="price_order",
    ),
    CheckConstraint(
        "expected_holding_trading_days IS NULL OR expected_holding_trading_days BETWEEN 1 AND 5",
        name="holding_days",
    ),
    CheckConstraint(
        "upside_probability IS NULL OR "
        "(upside_probability BETWEEN 0 AND 1 "
        "AND target_probability BETWEEN 0 AND 1 "
        "AND stop_probability BETWEEN 0 AND 1)",
        name="probabilities",
    ),
    CheckConstraint(
        "target_probability IS NULL OR target_probability + stop_probability <= 1",
        name="target_stop_probability",
    ),
    CheckConstraint(
        "expected_value_rate IS NULL OR expected_value_rate > 0",
        name="expected_value_positive",
    ),
    CheckConstraint(
        "reward_risk_ratio IS NULL OR reward_risk_ratio > 0",
        name="reward_risk_positive",
    ),
    CheckConstraint(
        "confidence IS NULL OR confidence BETWEEN 0 AND 1",
        name="confidence",
    ),
    CheckConstraint(
        "valid_until IS NULL OR valid_until > generated_at",
        name="valid_until",
    ),
    CheckConstraint(
        f"disposition NOT IN ({_ACTIONABLE}) OR risk_codes <> '[]'",
        name="actionable_risk_nonempty",
    ),
    CheckConstraint(
        f"disposition NOT IN ({_ACTIONABLE}) OR invalidation_codes <> '[]'",
        name="actionable_invalidation_nonempty",
    ),
    CheckConstraint(
        f"disposition NOT IN ({_NON_ACTIONABLE}) OR invalidation_codes = '[]'",
        name="non_actionable_invalidation_empty",
    ),
    CheckConstraint(
        "disposition <> 'MARKET_RISK' OR risk_codes <> '[]'",
        name="market_risk_nonempty",
    ),
    CheckConstraint(
        "DATALENGTH(recommendation_key) = 82 "
        "AND recommendation_key LIKE 'recommendation:v1:%' "
        "AND RIGHT(recommendation_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="recommendation_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 "
        "AND content_digest COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("recommendation_key", name="uq_recommendations_recommendation_key"),
    UniqueConstraint(
        "feature_snapshot_id",
        "generator_code",
        "generator_version",
        name="uq_recommendations_semantic_identity",
    ),
    schema=SCHEMA,
)
Index(
    "ix_recommendations_feature_snapshot_id",
    recommendations.c.feature_snapshot_id,
)
Index(
    "ix_recommendations_disposition_generated_at",
    recommendations.c.disposition,
    recommendations.c.generated_at,
)
Index(
    "ix_recommendations_generator_generated_at",
    recommendations.c.generator_code,
    recommendations.c.generator_version,
    recommendations.c.generated_at,
)
Index("ix_recommendations_generated_at", recommendations.c.generated_at)
