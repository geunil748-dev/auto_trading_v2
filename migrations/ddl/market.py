"""Frozen initial DDL for market, candidate, and filter evaluation tables."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    decimal_type,
    json_object_check,
    json_type,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def create_market_tables(op: Operations) -> None:
    """Create the first three canonical tables and their indexes."""

    op.create_table(
        "market_snapshots",
        sa.Column("market_snapshot_id", uuid_type(), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("observed_at", timestamp_type(), nullable=False),
        sa.Column("source", code_type(64), nullable=False),
        sa.Column("open_price", decimal_type(), nullable=False),
        sa.Column("high_price", decimal_type(), nullable=False),
        sa.Column("low_price", decimal_type(), nullable=False),
        sa.Column("last_price", decimal_type(), nullable=False),
        sa.Column("previous_high_price", decimal_type(), nullable=False),
        sa.Column("previous_low_price", decimal_type(), nullable=False),
        sa.Column("previous_close_price", decimal_type(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("market_snapshot_id", name="pk_market_snapshots"),
        sa.CheckConstraint(symbol_check(), name="ck_market_snapshots_symbol"),
        sa.CheckConstraint(
            "open_price > 0 AND high_price > 0 AND low_price > 0 "
            "AND last_price > 0 AND previous_high_price > 0 AND previous_low_price > 0",
            name="ck_market_snapshots_required_prices_positive",
        ),
        sa.CheckConstraint(
            "previous_close_price IS NULL OR previous_close_price > 0",
            name="ck_market_snapshots_previous_close_positive",
        ),
        sa.CheckConstraint(
            "volume IS NULL OR volume >= 0",
            name="ck_market_snapshots_volume_nonnegative",
        ),
        sa.CheckConstraint(
            "high_price >= low_price AND high_price >= open_price "
            "AND high_price >= last_price AND low_price <= open_price "
            "AND low_price <= last_price",
            name="ck_market_snapshots_ohlc_consistent",
        ),
        sa.CheckConstraint(
            "previous_high_price >= previous_low_price",
            name="ck_market_snapshots_previous_range_consistent",
        ),
        sa.UniqueConstraint(
            "source",
            "symbol",
            "observed_at",
            name="uq_market_snapshots_source_symbol_observed",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_snapshots_symbol_observed",
        "market_snapshots",
        ["symbol", "observed_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_snapshots_session_symbol",
        "market_snapshots",
        ["session_date", "symbol"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_snapshots_source_observed",
        "market_snapshots",
        ["source", "observed_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "candidates",
        sa.Column("candidate_id", uuid_type(), nullable=False),
        sa.Column("run_id", uuid_type(), nullable=False),
        sa.Column("market_snapshot_id", uuid_type(), nullable=False),
        sa.Column("candidate_source", code_type(64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("source_score", decimal_type(), nullable=True),
        sa.Column("selected_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("candidate_id", name="pk_candidates"),
        sa.ForeignKeyConstraint(
            ["market_snapshot_id"],
            ["trading.market_snapshots.market_snapshot_id"],
            name="fk_candidates_market_snapshot_id_market_snapshots",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint("rank IS NULL OR rank > 0", name="ck_candidates_rank_positive"),
        sa.UniqueConstraint(
            "run_id",
            "market_snapshot_id",
            "candidate_source",
            name="uq_candidates_run_snapshot_source",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_candidates_run_selected",
        "candidates",
        ["run_id", "selected_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_candidates_market_snapshot",
        "candidates",
        ["market_snapshot_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_candidates_source_selected",
        "candidates",
        ["candidate_source", "selected_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "filter_evaluations",
        sa.Column("filter_evaluation_id", uuid_type(), nullable=False),
        sa.Column("candidate_id", uuid_type(), nullable=False),
        sa.Column("filter_set_id", uuid_type(), nullable=False),
        sa.Column("evaluation_version", code_type(64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", decimal_type(), nullable=True),
        sa.Column("details", json_type(), nullable=False),
        sa.Column("evaluated_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("filter_evaluation_id", name="pk_filter_evaluations"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["trading.candidates.candidate_id"],
            name="fk_filter_evaluations_candidate_id_candidates",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            json_object_check("details"),
            name="ck_filter_evaluations_details_json_object",
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "filter_set_id",
            "evaluation_version",
            name="uq_filter_evaluations_candidate_set_version",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_filter_evaluations_candidate",
        "filter_evaluations",
        ["candidate_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_filter_evaluations_set_evaluated",
        "filter_evaluations",
        ["filter_set_id", "evaluated_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_filter_evaluations_passed_evaluated",
        "filter_evaluations",
        ["passed", "evaluated_at"],
        schema=SCHEMA,
    )
