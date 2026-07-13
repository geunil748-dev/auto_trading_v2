"""Canonical cross-stage trading event timeline table."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Table, UniqueConstraint

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    json_object_check_sql,
    json_text_type,
    non_empty_check_sql,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

trading_events = Table(
    "trading_events",
    metadata,
    Column("event_id", uuid_type(), primary_key=True),
    Column("dedup_key", code_type(200), nullable=False),
    Column("event_type", code_type(80), nullable=False),
    Column("stage", code_type(40), nullable=False),
    Column("severity", code_type(16), nullable=False),
    Column("occurred_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    Column("correlation_id", uuid_type(), nullable=True),
    Column(
        "causation_event_id",
        uuid_type(),
        ForeignKey(
            "trading.trading_events.event_id",
            name="fk_trading_events_causation_event_id_trading_events",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column("run_id", uuid_type(), nullable=True),
    Column("strategy_id", uuid_type(), nullable=True),
    Column("symbol", symbol_type(), nullable=True),
    Column(
        "market_snapshot_id",
        uuid_type(),
        ForeignKey(
            "trading.market_snapshots.market_snapshot_id",
            name="fk_trading_events_market_snapshot_id_market_snapshots",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "candidate_id",
        uuid_type(),
        ForeignKey(
            "trading.candidates.candidate_id",
            name="fk_trading_events_candidate_id_candidates",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "filter_evaluation_id",
        uuid_type(),
        ForeignKey(
            "trading.filter_evaluations.filter_evaluation_id",
            name="fk_trading_events_filter_evaluation_id_filter_evaluations",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "decision_id",
        uuid_type(),
        ForeignKey(
            "trading.strategy_decisions.decision_id",
            name="fk_trading_events_decision_id_strategy_decisions",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "trade_intent_id",
        uuid_type(),
        ForeignKey(
            "trading.trade_intents.trade_intent_id",
            name="fk_trading_events_trade_intent_id_trade_intents",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "order_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_orders.order_id",
            name="fk_trading_events_order_id_paper_orders",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "fill_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_fills.fill_id",
            name="fk_trading_events_fill_id_paper_fills",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "position_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_positions.position_id",
            name="fk_trading_events_position_id_paper_positions",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "equity_snapshot_id",
        uuid_type(),
        ForeignKey(
            "trading.equity_snapshots.equity_snapshot_id",
            name="fk_trading_events_equity_snapshot_id_equity_snapshots",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column("payload", json_text_type(), nullable=False),
    CheckConstraint(non_empty_check_sql("event_type"), name="event_type_nonempty"),
    CheckConstraint(non_empty_check_sql("stage"), name="stage_nonempty"),
    CheckConstraint(
        "severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')",
        name="severity",
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint(json_object_check_sql("payload"), name="payload_json_object"),
    UniqueConstraint("dedup_key", name="uq_trading_events_dedup_key"),
    schema=SCHEMA,
)
Index("ix_trading_events_occurred", trading_events.c.occurred_at)
Index("ix_trading_events_run_occurred", trading_events.c.run_id, trading_events.c.occurred_at)
Index(
    "ix_trading_events_strategy_occurred",
    trading_events.c.strategy_id,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_symbol_occurred",
    trading_events.c.symbol,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_type_occurred",
    trading_events.c.event_type,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_candidate_occurred",
    trading_events.c.candidate_id,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_decision_occurred",
    trading_events.c.decision_id,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_order_occurred",
    trading_events.c.order_id,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_position_occurred",
    trading_events.c.position_id,
    trading_events.c.occurred_at,
)
Index(
    "ix_trading_events_correlation_occurred",
    trading_events.c.correlation_id,
    trading_events.c.occurred_at,
)
