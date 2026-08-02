"""Canonical immutable P4A scoring run and item tables."""

from sqlalchemy import (
    DECIMAL,
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
    non_empty_check_sql,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"
_SCORE_COLUMNS = (
    "momentum_score",
    "trend_score",
    "breakout_score",
    "price_action_score",
    "stability_score",
    "volume_score",
    "overall_relative_score",
)

daily_feature_scoring_runs = Table(
    "daily_feature_scoring_runs",
    metadata,
    Column("daily_feature_scoring_run_id", uuid_type(), primary_key=True),
    Column("scoring_run_key", code_type(93), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
    Column("scoring_policy_code", code_type(64), nullable=False),
    Column("scoring_policy_version", code_type(64), nullable=False),
    Column("ranking_policy_code", code_type(64), nullable=False),
    Column("ranking_policy_version", code_type(64), nullable=False),
    Column("status", code_type(32), nullable=False),
    Column("total_count", SmallInteger(), nullable=False),
    Column("scored_ready_count", SmallInteger(), nullable=False),
    Column("scored_degraded_count", SmallInteger(), nullable=False),
    Column("unscorable_count", SmallInteger(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_run_id"],
        ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
        name="fk_daily_feature_scoring_runs_source_pipeline_run_id_runs",
        ondelete="NO ACTION",
    ),
    CheckConstraint(non_empty_check_sql("scoring_policy_code"), name="scoring_policy_code"),
    CheckConstraint(non_empty_check_sql("scoring_policy_version"), name="scoring_policy_version"),
    CheckConstraint(non_empty_check_sql("ranking_policy_code"), name="ranking_policy_code"),
    CheckConstraint(non_empty_check_sql("ranking_policy_version"), name="ranking_policy_version"),
    CheckConstraint(
        "status IN ('COMPLETED','COMPLETED_WITH_UNSCORABLE','NO_SCORABLE_ITEMS')",
        name="status",
    ),
    CheckConstraint(
        "total_count BETWEEN 0 AND 100 AND scored_ready_count BETWEEN 0 AND 100 "
        "AND scored_degraded_count BETWEEN 0 AND 100 AND unscorable_count BETWEEN 0 AND 100",
        name="counts",
    ),
    CheckConstraint(
        "total_count = scored_ready_count + scored_degraded_count + unscorable_count",
        name="count_sum",
    ),
    CheckConstraint(
        "(status = 'COMPLETED' AND unscorable_count = 0) OR "
        "(status = 'COMPLETED_WITH_UNSCORABLE' "
        "AND scored_ready_count + scored_degraded_count > 0 AND unscorable_count > 0) OR "
        "(status = 'NO_SCORABLE_ITEMS' AND scored_ready_count = 0 AND scored_degraded_count = 0)",
        name="status_shape",
    ),
    CheckConstraint("generated_at <= recorded_at", name="time_order"),
    CheckConstraint(
        "DATALENGTH(scoring_run_key) = 93 "
        "AND scoring_run_key LIKE 'daily-feature-scoring-run:v1:%' "
        "AND RIGHT(scoring_run_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="scoring_run_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 AND content_digest "
        "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("scoring_run_key", name="uq_daily_feature_scoring_runs_key"),
    UniqueConstraint(
        "source_daily_feature_pipeline_run_id",
        "scoring_policy_code",
        "scoring_policy_version",
        "ranking_policy_code",
        "ranking_policy_version",
        name="uq_daily_feature_scoring_runs_source_policies",
    ),
    schema=SCHEMA,
)

daily_feature_scoring_items = Table(
    "daily_feature_scoring_items",
    metadata,
    Column("daily_feature_scoring_item_id", uuid_type(), primary_key=True),
    Column("daily_feature_scoring_run_id", uuid_type(), nullable=False),
    Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
    Column("ordinal", SmallInteger(), nullable=False),
    Column("rank", SmallInteger(), nullable=True),
    Column("symbol", symbol_type(), nullable=False),
    Column("mic_code", code_type(4), nullable=False),
    Column("feature_snapshot_id", uuid_type(), nullable=True),
    Column("source_quality_status", code_type(16), nullable=True),
    Column("outcome", code_type(32), nullable=False),
    *(Column(name, DECIMAL(9, 6), nullable=True) for name in _SCORE_COLUMNS),
    Column("safe_reason_code", code_type(96), nullable=True),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    ForeignKeyConstraint(
        ["daily_feature_scoring_run_id"],
        ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
        name="fk_daily_feature_scoring_items_scoring_run_id_runs",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["source_daily_feature_pipeline_item_id"],
        ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
        name="fk_daily_feature_scoring_items_source_pipeline_item_id_items",
        ondelete="NO ACTION",
    ),
    ForeignKeyConstraint(
        ["feature_snapshot_id"],
        ["trading.feature_snapshots.feature_snapshot_id"],
        name="fk_daily_feature_scoring_items_feature_snapshot_id_snapshots",
        ondelete="NO ACTION",
    ),
    CheckConstraint("ordinal BETWEEN 1 AND 100", name="ordinal"),
    CheckConstraint("rank IS NULL OR rank BETWEEN 1 AND 100", name="rank"),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint("mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", name="mic_code"),
    CheckConstraint(
        "source_quality_status IS NULL OR source_quality_status IN ('READY','DEGRADED')",
        name="source_quality",
    ),
    CheckConstraint(
        "outcome IN ('SCORED_READY','SCORED_DEGRADED','SOURCE_ITEM_NOT_SCORABLE',"
        "'FEATURE_SNAPSHOT_MISSING','FEATURE_SOURCE_MISMATCH','FEATURE_CONTRACT_INVALID',"
        "'FEATURE_QUALITY_UNSUPPORTED')",
        name="outcome",
    ),
    *(
        CheckConstraint(f"{name} IS NULL OR {name} BETWEEN 0 AND 100", name=name)
        for name in _SCORE_COLUMNS
    ),
    CheckConstraint(
        "(outcome = 'SCORED_READY' AND feature_snapshot_id IS NOT NULL "
        "AND source_quality_status = 'READY' AND rank IS NOT NULL "
        "AND momentum_score IS NOT NULL AND trend_score IS NOT NULL "
        "AND breakout_score IS NOT NULL AND price_action_score IS NOT NULL "
        "AND stability_score IS NOT NULL AND volume_score IS NOT NULL "
        "AND overall_relative_score IS NOT NULL) OR "
        "(outcome = 'SCORED_DEGRADED' AND feature_snapshot_id IS NOT NULL "
        "AND source_quality_status = 'DEGRADED' AND rank IS NOT NULL "
        "AND momentum_score IS NOT NULL AND trend_score IS NOT NULL "
        "AND breakout_score IS NOT NULL AND price_action_score IS NOT NULL "
        "AND stability_score IS NOT NULL AND volume_score IS NULL "
        "AND overall_relative_score IS NOT NULL) OR "
        "(outcome NOT IN ('SCORED_READY','SCORED_DEGRADED') AND rank IS NULL "
        "AND momentum_score IS NULL AND trend_score IS NULL AND breakout_score IS NULL "
        "AND price_action_score IS NULL AND stability_score IS NULL AND volume_score IS NULL "
        "AND overall_relative_score IS NULL AND safe_reason_code IS NOT NULL)",
        name="outcome_shape",
    ),
    CheckConstraint("generated_at <= recorded_at", name="time_order"),
    UniqueConstraint(
        "daily_feature_scoring_run_id", "ordinal", name="uq_daily_feature_scoring_items_run_ordinal"
    ),
    UniqueConstraint(
        "daily_feature_scoring_run_id",
        "source_daily_feature_pipeline_item_id",
        name="uq_daily_feature_scoring_items_run_source_item",
    ),
    UniqueConstraint(
        "daily_feature_scoring_run_id", "symbol", name="uq_daily_feature_scoring_items_run_symbol"
    ),
    schema=SCHEMA,
)

Index(
    "ix_daily_feature_scoring_runs_source",
    daily_feature_scoring_runs.c.source_daily_feature_pipeline_run_id,
)
Index(
    "ix_daily_feature_scoring_runs_status_generated",
    daily_feature_scoring_runs.c.status,
    daily_feature_scoring_runs.c.generated_at,
)
Index(
    "ix_daily_feature_scoring_runs_policy_generated",
    daily_feature_scoring_runs.c.scoring_policy_code,
    daily_feature_scoring_runs.c.scoring_policy_version,
    daily_feature_scoring_runs.c.generated_at,
)
Index(
    "ix_daily_feature_scoring_items_run_rank",
    daily_feature_scoring_items.c.daily_feature_scoring_run_id,
    daily_feature_scoring_items.c.rank,
)
Index(
    "ix_daily_feature_scoring_items_symbol_generated",
    daily_feature_scoring_items.c.symbol,
    daily_feature_scoring_items.c.generated_at,
)
Index(
    "ix_daily_feature_scoring_items_outcome_generated",
    daily_feature_scoring_items.c.outcome,
    daily_feature_scoring_items.c.generated_at,
)
Index(
    "ix_daily_feature_scoring_items_feature_snapshot",
    daily_feature_scoring_items.c.feature_snapshot_id,
)
Index(
    "ix_daily_feature_scoring_items_overall", daily_feature_scoring_items.c.overall_relative_score
)
