"""Canonical market observation, candidate, and filter-evaluation tables."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Table,
    UniqueConstraint,
)

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    decimal_type,
    json_object_check_sql,
    json_text_type,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

market_snapshots = Table(
    "market_snapshots",
    metadata,
    Column("market_snapshot_id", uuid_type(), primary_key=True),
    Column("symbol", symbol_type(), nullable=False),
    Column("session_date", Date(), nullable=False),
    Column("observed_at", timestamp_type(), nullable=False),
    Column("source", code_type(64), nullable=False),
    Column("open_price", decimal_type(), nullable=False),
    Column("high_price", decimal_type(), nullable=False),
    Column("low_price", decimal_type(), nullable=False),
    Column("last_price", decimal_type(), nullable=False),
    Column("previous_high_price", decimal_type(), nullable=False),
    Column("previous_low_price", decimal_type(), nullable=False),
    Column("previous_close_price", decimal_type(), nullable=True),
    Column("volume", BigInteger(), nullable=True),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint(
        "open_price > 0 AND high_price > 0 AND low_price > 0 "
        "AND last_price > 0 AND previous_high_price > 0 AND previous_low_price > 0",
        name="required_prices_positive",
    ),
    CheckConstraint(
        "previous_close_price IS NULL OR previous_close_price > 0",
        name="previous_close_positive",
    ),
    CheckConstraint("volume IS NULL OR volume >= 0", name="volume_nonnegative"),
    CheckConstraint(
        "high_price >= low_price AND high_price >= open_price "
        "AND high_price >= last_price AND low_price <= open_price "
        "AND low_price <= last_price",
        name="ohlc_consistent",
    ),
    CheckConstraint(
        "previous_high_price >= previous_low_price",
        name="previous_range_consistent",
    ),
    UniqueConstraint(
        "source",
        "symbol",
        "observed_at",
        name="uq_market_snapshots_source_symbol_observed",
    ),
    schema=SCHEMA,
)
Index(
    "ix_market_snapshots_symbol_observed",
    market_snapshots.c.symbol,
    market_snapshots.c.observed_at,
)
Index(
    "ix_market_snapshots_session_symbol",
    market_snapshots.c.session_date,
    market_snapshots.c.symbol,
)
Index(
    "ix_market_snapshots_source_observed",
    market_snapshots.c.source,
    market_snapshots.c.observed_at,
)

candidates = Table(
    "candidates",
    metadata,
    Column("candidate_id", uuid_type(), primary_key=True),
    Column("run_id", uuid_type(), nullable=False),
    Column(
        "market_snapshot_id",
        uuid_type(),
        ForeignKey(
            "trading.market_snapshots.market_snapshot_id",
            name="fk_candidates_market_snapshot_id_market_snapshots",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column("candidate_source", code_type(64), nullable=False),
    Column("rank", Integer(), nullable=True),
    Column("source_score", decimal_type(), nullable=True),
    Column("selected_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint("rank IS NULL OR rank > 0", name="rank_positive"),
    UniqueConstraint(
        "run_id",
        "market_snapshot_id",
        "candidate_source",
        name="uq_candidates_run_snapshot_source",
    ),
    schema=SCHEMA,
)
Index("ix_candidates_run_selected", candidates.c.run_id, candidates.c.selected_at)
Index("ix_candidates_market_snapshot", candidates.c.market_snapshot_id)
Index(
    "ix_candidates_source_selected",
    candidates.c.candidate_source,
    candidates.c.selected_at,
)

filter_evaluations = Table(
    "filter_evaluations",
    metadata,
    Column("filter_evaluation_id", uuid_type(), primary_key=True),
    Column(
        "candidate_id",
        uuid_type(),
        ForeignKey(
            "trading.candidates.candidate_id",
            name="fk_filter_evaluations_candidate_id_candidates",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column("filter_set_id", uuid_type(), nullable=False),
    Column("evaluation_version", code_type(64), nullable=False),
    Column("passed", Boolean(), nullable=False),
    Column("score", decimal_type(), nullable=True),
    Column("details", json_text_type(), nullable=False),
    Column("evaluated_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(json_object_check_sql("details"), name="details_json_object"),
    UniqueConstraint(
        "candidate_id",
        "filter_set_id",
        "evaluation_version",
        name="uq_filter_evaluations_candidate_set_version",
    ),
    schema=SCHEMA,
)
Index("ix_filter_evaluations_candidate", filter_evaluations.c.candidate_id)
Index(
    "ix_filter_evaluations_set_evaluated",
    filter_evaluations.c.filter_set_id,
    filter_evaluations.c.evaluated_at,
)
Index(
    "ix_filter_evaluations_passed_evaluated",
    filter_evaluations.c.passed,
    filter_evaluations.c.evaluated_at,
)
