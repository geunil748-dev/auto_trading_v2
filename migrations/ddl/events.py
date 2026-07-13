"""Frozen initial DDL for the unified trading event timeline."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    json_object_check,
    json_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def create_trading_events(op: Operations) -> None:
    """Create the canonical cross-stage event timeline and query indexes."""

    op.create_table(
        "trading_events",
        sa.Column("event_id", uuid_type(), nullable=False),
        sa.Column("dedup_key", code_type(200), nullable=False),
        sa.Column("event_type", code_type(80), nullable=False),
        sa.Column("stage", code_type(40), nullable=False),
        sa.Column("severity", code_type(16), nullable=False),
        sa.Column("occurred_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.Column("correlation_id", uuid_type(), nullable=True),
        sa.Column("causation_event_id", uuid_type(), nullable=True),
        sa.Column("run_id", uuid_type(), nullable=True),
        sa.Column("strategy_id", uuid_type(), nullable=True),
        sa.Column("symbol", symbol_type(), nullable=True),
        sa.Column("market_snapshot_id", uuid_type(), nullable=True),
        sa.Column("candidate_id", uuid_type(), nullable=True),
        sa.Column("filter_evaluation_id", uuid_type(), nullable=True),
        sa.Column("decision_id", uuid_type(), nullable=True),
        sa.Column("trade_intent_id", uuid_type(), nullable=True),
        sa.Column("order_id", uuid_type(), nullable=True),
        sa.Column("fill_id", uuid_type(), nullable=True),
        sa.Column("position_id", uuid_type(), nullable=True),
        sa.Column("equity_snapshot_id", uuid_type(), nullable=True),
        sa.Column("payload", json_type(), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_trading_events"),
        sa.ForeignKeyConstraint(
            ["causation_event_id"],
            ["trading.trading_events.event_id"],
            name="fk_trading_events_causation_event_id_trading_events",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["market_snapshot_id"],
            ["trading.market_snapshots.market_snapshot_id"],
            name="fk_trading_events_market_snapshot_id_market_snapshots",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["trading.candidates.candidate_id"],
            name="fk_trading_events_candidate_id_candidates",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["filter_evaluation_id"],
            ["trading.filter_evaluations.filter_evaluation_id"],
            name="fk_trading_events_filter_evaluation_id_filter_evaluations",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["trading.strategy_decisions.decision_id"],
            name="fk_trading_events_decision_id_strategy_decisions",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["trade_intent_id"],
            ["trading.trade_intents.trade_intent_id"],
            name="fk_trading_events_trade_intent_id_trade_intents",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["trading.paper_orders.order_id"],
            name="fk_trading_events_order_id_paper_orders",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["fill_id"],
            ["trading.paper_fills.fill_id"],
            name="fk_trading_events_fill_id_paper_fills",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["trading.paper_positions.position_id"],
            name="fk_trading_events_position_id_paper_positions",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["equity_snapshot_id"],
            ["trading.equity_snapshots.equity_snapshot_id"],
            name="fk_trading_events_equity_snapshot_id_equity_snapshots",
            ondelete="NO ACTION",
        ),
        named_check_constraint(
            "DATALENGTH(LTRIM(RTRIM(event_type))) > 0",
            name="ck_trading_events_event_type_nonempty",
        ),
        named_check_constraint(
            "DATALENGTH(LTRIM(RTRIM(stage))) > 0",
            name="ck_trading_events_stage_nonempty",
        ),
        named_check_constraint(
            "severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')",
            name="ck_trading_events_severity",
        ),
        named_check_constraint(symbol_check(), name="ck_trading_events_symbol"),
        named_check_constraint(
            json_object_check("payload"),
            name="ck_trading_events_payload_json_object",
        ),
        sa.UniqueConstraint("dedup_key", name="uq_trading_events_dedup_key"),
        schema=SCHEMA,
    )
    _create_indexes(op)


def _create_indexes(op: Operations) -> None:
    indexes = (
        ("ix_trading_events_occurred", ["occurred_at"]),
        ("ix_trading_events_run_occurred", ["run_id", "occurred_at"]),
        ("ix_trading_events_strategy_occurred", ["strategy_id", "occurred_at"]),
        ("ix_trading_events_symbol_occurred", ["symbol", "occurred_at"]),
        ("ix_trading_events_type_occurred", ["event_type", "occurred_at"]),
        ("ix_trading_events_candidate_occurred", ["candidate_id", "occurred_at"]),
        ("ix_trading_events_decision_occurred", ["decision_id", "occurred_at"]),
        ("ix_trading_events_order_occurred", ["order_id", "occurred_at"]),
        ("ix_trading_events_position_occurred", ["position_id", "occurred_at"]),
        ("ix_trading_events_correlation_occurred", ["correlation_id", "occurred_at"]),
    )
    for name, columns in indexes:
        op.create_index(name, "trading_events", columns, schema=SCHEMA)
