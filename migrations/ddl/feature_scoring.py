"""Additive DDL for P4A immutable relative-scoring aggregates."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)

_SCORES = (
    "momentum_score",
    "trend_score",
    "breakout_score",
    "price_action_score",
    "stability_score",
    "volume_score",
    "overall_relative_score",
)


def _check(table: str, sql: str, suffix: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_{table}_{suffix}")


def _create_runs(op: Operations) -> None:
    table = "daily_feature_scoring_runs"
    op.create_table(
        "daily_feature_scoring_runs",
        sa.Column("daily_feature_scoring_run_id", uuid_type(), nullable=False),
        sa.Column("scoring_run_key", code_type(93), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("source_daily_feature_pipeline_run_id", uuid_type(), nullable=False),
        sa.Column("scoring_policy_code", code_type(64), nullable=False),
        sa.Column("scoring_policy_version", code_type(64), nullable=False),
        sa.Column("ranking_policy_code", code_type(64), nullable=False),
        sa.Column("ranking_policy_version", code_type(64), nullable=False),
        sa.Column("status", code_type(32), nullable=False),
        sa.Column("total_count", sa.SmallInteger(), nullable=False),
        sa.Column("scored_ready_count", sa.SmallInteger(), nullable=False),
        sa.Column("scored_degraded_count", sa.SmallInteger(), nullable=False),
        sa.Column("unscorable_count", sa.SmallInteger(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_scoring_run_id", name="pk_daily_feature_scoring_runs"
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_run_id"],
            ["trading.daily_feature_pipeline_runs.daily_feature_pipeline_run_id"],
            name="fk_daily_feature_scoring_runs_source_pipeline_run_id_runs",
            ondelete="NO ACTION",
        ),
        _check(table, "DATALENGTH(LTRIM(RTRIM(scoring_policy_code))) > 0", "scoring_policy_code"),
        _check(
            table,
            "DATALENGTH(LTRIM(RTRIM(scoring_policy_version))) > 0",
            "scoring_policy_version",
        ),
        _check(table, "DATALENGTH(LTRIM(RTRIM(ranking_policy_code))) > 0", "ranking_policy_code"),
        _check(
            table,
            "DATALENGTH(LTRIM(RTRIM(ranking_policy_version))) > 0",
            "ranking_policy_version",
        ),
        _check(
            table,
            "status IN ('COMPLETED','COMPLETED_WITH_UNSCORABLE','NO_SCORABLE_ITEMS')",
            "status",
        ),
        _check(
            table,
            "total_count BETWEEN 0 AND 100 AND scored_ready_count BETWEEN 0 AND 100 "
            "AND scored_degraded_count BETWEEN 0 AND 100 AND unscorable_count BETWEEN 0 AND 100",
            "counts",
        ),
        _check(
            table,
            "total_count = scored_ready_count + scored_degraded_count + unscorable_count",
            "count_sum",
        ),
        _check(
            table,
            "(status = 'COMPLETED' AND unscorable_count = 0) OR "
            "(status = 'COMPLETED_WITH_UNSCORABLE' "
            "AND scored_ready_count + scored_degraded_count > 0 AND unscorable_count > 0) OR "
            "(status = 'NO_SCORABLE_ITEMS' AND scored_ready_count = 0 "
            "AND scored_degraded_count = 0)",
            "status_shape",
        ),
        _check(table, "generated_at <= recorded_at", "time_order"),
        _check(
            table,
            "DATALENGTH(scoring_run_key) = 93 "
            "AND scoring_run_key LIKE 'daily-feature-scoring-run:v1:%' "
            "AND RIGHT(scoring_run_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "scoring_run_key_format",
        ),
        _check(
            table,
            "DATALENGTH(content_digest) = 64 AND content_digest "
            "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        sa.UniqueConstraint("scoring_run_key", name="uq_daily_feature_scoring_runs_key"),
        sa.UniqueConstraint(
            "source_daily_feature_pipeline_run_id",
            "scoring_policy_code",
            "scoring_policy_version",
            "ranking_policy_code",
            "ranking_policy_version",
            name="uq_daily_feature_scoring_runs_source_policies",
        ),
        schema=SCHEMA,
    )
    for name, columns in (
        ("ix_daily_feature_scoring_runs_source", ["source_daily_feature_pipeline_run_id"]),
        ("ix_daily_feature_scoring_runs_status_generated", ["status", "generated_at"]),
        (
            "ix_daily_feature_scoring_runs_policy_generated",
            ["scoring_policy_code", "scoring_policy_version", "generated_at"],
        ),
    ):
        op.create_index(name, table, columns, schema=SCHEMA)


def _item_shape() -> str:
    return (
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
        "AND overall_relative_score IS NULL AND safe_reason_code IS NOT NULL)"
    )


def _create_items(op: Operations) -> None:
    table = "daily_feature_scoring_items"
    op.create_table(
        "daily_feature_scoring_items",
        sa.Column("daily_feature_scoring_item_id", uuid_type(), nullable=False),
        sa.Column("daily_feature_scoring_run_id", uuid_type(), nullable=False),
        sa.Column("source_daily_feature_pipeline_item_id", uuid_type(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("mic_code", code_type(4), nullable=False),
        sa.Column("feature_snapshot_id", uuid_type(), nullable=True),
        sa.Column("source_quality_status", code_type(16), nullable=True),
        sa.Column("outcome", code_type(32), nullable=False),
        sa.Column("momentum_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("trend_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("breakout_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("price_action_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("stability_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("volume_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("overall_relative_score", sa.DECIMAL(9, 6), nullable=True),
        sa.Column("safe_reason_code", code_type(96), nullable=True),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint(
            "daily_feature_scoring_item_id", name="pk_daily_feature_scoring_items"
        ),
        sa.ForeignKeyConstraint(
            ["daily_feature_scoring_run_id"],
            ["trading.daily_feature_scoring_runs.daily_feature_scoring_run_id"],
            name="fk_daily_feature_scoring_items_scoring_run_id_runs",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_feature_pipeline_item_id"],
            ["trading.daily_feature_pipeline_items.daily_feature_pipeline_item_id"],
            name="fk_daily_feature_scoring_items_source_pipeline_item_id_items",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["trading.feature_snapshots.feature_snapshot_id"],
            name="fk_daily_feature_scoring_items_feature_snapshot_id_snapshots",
            ondelete="NO ACTION",
        ),
        _check(table, "ordinal BETWEEN 1 AND 100", "ordinal"),
        _check(table, "rank IS NULL OR rank BETWEEN 1 AND 100", "rank"),
        _check(table, symbol_check(), "symbol"),
        _check(table, "mic_code IN ('XNGS','XNGM','XNCM','XNYS','XASE')", "mic_code"),
        _check(
            table,
            "source_quality_status IS NULL OR source_quality_status IN ('READY','DEGRADED')",
            "source_quality",
        ),
        _check(
            table,
            "outcome IN ('SCORED_READY','SCORED_DEGRADED','SOURCE_ITEM_NOT_SCORABLE',"
            "'FEATURE_SNAPSHOT_MISSING','FEATURE_SOURCE_MISMATCH','FEATURE_CONTRACT_INVALID',"
            "'FEATURE_QUALITY_UNSUPPORTED')",
            "outcome",
        ),
        *(_check(table, f"{name} IS NULL OR {name} BETWEEN 0 AND 100", name) for name in _SCORES),
        _check(table, _item_shape(), "outcome_shape"),
        _check(table, "generated_at <= recorded_at", "time_order"),
        sa.UniqueConstraint(
            "daily_feature_scoring_run_id",
            "ordinal",
            name="uq_daily_feature_scoring_items_run_ordinal",
        ),
        sa.UniqueConstraint(
            "daily_feature_scoring_run_id",
            "source_daily_feature_pipeline_item_id",
            name="uq_daily_feature_scoring_items_run_source_item",
        ),
        sa.UniqueConstraint(
            "daily_feature_scoring_run_id",
            "symbol",
            name="uq_daily_feature_scoring_items_run_symbol",
        ),
        schema=SCHEMA,
    )
    for name, columns in (
        ("ix_daily_feature_scoring_items_run_rank", ["daily_feature_scoring_run_id", "rank"]),
        ("ix_daily_feature_scoring_items_symbol_generated", ["symbol", "generated_at"]),
        ("ix_daily_feature_scoring_items_outcome_generated", ["outcome", "generated_at"]),
        ("ix_daily_feature_scoring_items_feature_snapshot", ["feature_snapshot_id"]),
        ("ix_daily_feature_scoring_items_overall", ["overall_relative_score"]),
    ):
        op.create_index(name, table, columns, schema=SCHEMA)


def create_daily_feature_scoring_tables(op: Operations) -> None:
    """Create only the two P4A tables in dependency order."""

    _create_runs(op)
    _create_items(op)
