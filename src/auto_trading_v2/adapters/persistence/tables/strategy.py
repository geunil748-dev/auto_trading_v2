"""Canonical strategy-decision and immutable trade-intent tables."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Table,
    UniqueConstraint,
    text,
)

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    currency_check_sql,
    currency_type,
    decimal_type,
    json_array_check_sql,
    json_text_type,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

strategy_decisions = Table(
    "strategy_decisions",
    metadata,
    Column("decision_id", uuid_type(), primary_key=True),
    Column("decision_key", code_type(160), nullable=False),
    Column(
        "candidate_id",
        uuid_type(),
        ForeignKey(
            "trading.candidates.candidate_id",
            name="fk_strategy_decisions_candidate_id_candidates",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "position_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_positions.position_id",
            name="fk_strategy_decisions_position_id_paper_positions",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column(
        "filter_evaluation_id",
        uuid_type(),
        ForeignKey(
            "trading.filter_evaluations.filter_evaluation_id",
            name="fk_strategy_decisions_filter_evaluation_id_filter_evaluations",
            ondelete="NO ACTION",
        ),
        nullable=True,
    ),
    Column("strategy_id", uuid_type(), nullable=False),
    Column("strategy_version", code_type(64), nullable=False),
    Column("action", code_type(32), nullable=False),
    Column("reason_codes", json_text_type(), nullable=False),
    Column("decided_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(
        "action IN ('ENTER_LONG', 'EXIT_LONG', 'SKIP', 'OBSERVE')",
        name="action",
    ),
    CheckConstraint(
        "(candidate_id IS NOT NULL AND position_id IS NULL) "
        "OR (candidate_id IS NULL AND position_id IS NOT NULL)",
        name="candidate_xor_position",
    ),
    CheckConstraint(
        "filter_evaluation_id IS NULL OR candidate_id IS NOT NULL",
        name="filter_requires_candidate",
    ),
    CheckConstraint(
        "position_id IS NULL OR filter_evaluation_id IS NULL",
        name="position_without_filter",
    ),
    CheckConstraint(json_array_check_sql("reason_codes"), name="reason_codes_json_array"),
    UniqueConstraint("decision_key", name="uq_strategy_decisions_decision_key"),
    schema=SCHEMA,
)
Index(
    "ix_strategy_decisions_candidate_unique",
    strategy_decisions.c.candidate_id,
    strategy_decisions.c.strategy_id,
    strategy_decisions.c.strategy_version,
    unique=True,
    mssql_where=text("candidate_id IS NOT NULL"),
)
Index(
    "ix_strategy_decisions_strategy_decided",
    strategy_decisions.c.strategy_id,
    strategy_decisions.c.decided_at,
)
Index("ix_strategy_decisions_candidate", strategy_decisions.c.candidate_id)
Index("ix_strategy_decisions_position", strategy_decisions.c.position_id)
Index(
    "ix_strategy_decisions_action_decided",
    strategy_decisions.c.action,
    strategy_decisions.c.decided_at,
)

trade_intents = Table(
    "trade_intents",
    metadata,
    Column("trade_intent_id", uuid_type(), primary_key=True),
    Column(
        "decision_id",
        uuid_type(),
        ForeignKey(
            "trading.strategy_decisions.decision_id",
            name="fk_trade_intents_decision_id_strategy_decisions",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column("idempotency_key", code_type(160), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("currency", currency_type(), nullable=False),
    Column("side", code_type(8), nullable=False),
    Column("order_type", code_type(16), nullable=False),
    Column("requested_quantity", BigInteger(), nullable=False),
    Column("limit_price", decimal_type(), nullable=True),
    Column("time_in_force", code_type(16), nullable=False),
    Column("created_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint(currency_check_sql(), name="currency"),
    CheckConstraint("side IN ('BUY', 'SELL')", name="side"),
    CheckConstraint("order_type IN ('MARKET', 'LIMIT')", name="order_type"),
    CheckConstraint("time_in_force = 'DAY'", name="time_in_force"),
    CheckConstraint("requested_quantity > 0", name="quantity_positive"),
    CheckConstraint(
        "(order_type = 'MARKET' AND limit_price IS NULL) "
        "OR (order_type = 'LIMIT' AND limit_price IS NOT NULL AND limit_price > 0)",
        name="limit_price_by_order_type",
    ),
    UniqueConstraint("decision_id", name="uq_trade_intents_decision_id"),
    UniqueConstraint("idempotency_key", name="uq_trade_intents_idempotency_key"),
    schema=SCHEMA,
)
Index("ix_trade_intents_created", trade_intents.c.created_at)
Index(
    "ix_trade_intents_symbol_created",
    trade_intents.c.symbol,
    trade_intents.c.created_at,
)
Index(
    "ix_trade_intents_side_created",
    trade_intents.c.side,
    trade_intents.c.created_at,
)
