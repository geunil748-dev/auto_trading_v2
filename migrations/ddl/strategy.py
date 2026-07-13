"""Frozen initial DDL for strategy decisions and trade intents."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    currency_check,
    currency_type,
    decimal_type,
    json_array_check,
    json_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def create_strategy_tables(op: Operations) -> None:
    """Create canonical strategy decision and immutable intent tables."""

    op.create_table(
        "strategy_decisions",
        sa.Column("decision_id", uuid_type(), nullable=False),
        sa.Column("decision_key", code_type(160), nullable=False),
        sa.Column("candidate_id", uuid_type(), nullable=True),
        sa.Column("position_id", uuid_type(), nullable=True),
        sa.Column("filter_evaluation_id", uuid_type(), nullable=True),
        sa.Column("strategy_id", uuid_type(), nullable=False),
        sa.Column("strategy_version", code_type(64), nullable=False),
        sa.Column("action", code_type(32), nullable=False),
        sa.Column("reason_codes", json_type(), nullable=False),
        sa.Column("decided_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("decision_id", name="pk_strategy_decisions"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["trading.candidates.candidate_id"],
            name="fk_strategy_decisions_candidate_id_candidates",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["trading.paper_positions.position_id"],
            name="fk_strategy_decisions_position_id_paper_positions",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["filter_evaluation_id"],
            ["trading.filter_evaluations.filter_evaluation_id"],
            name="fk_strategy_decisions_filter_evaluation_id_filter_evaluations",
            ondelete="NO ACTION",
        ),
        named_check_constraint(
            "action IN ('ENTER_LONG', 'EXIT_LONG', 'SKIP', 'OBSERVE')",
            name="ck_strategy_decisions_action",
        ),
        named_check_constraint(
            "(candidate_id IS NOT NULL AND position_id IS NULL) "
            "OR (candidate_id IS NULL AND position_id IS NOT NULL)",
            name="ck_strategy_decisions_candidate_xor_position",
        ),
        named_check_constraint(
            "filter_evaluation_id IS NULL OR candidate_id IS NOT NULL",
            name="ck_strategy_decisions_filter_requires_candidate",
        ),
        named_check_constraint(
            "position_id IS NULL OR filter_evaluation_id IS NULL",
            name="ck_strategy_decisions_position_without_filter",
        ),
        named_check_constraint(
            json_array_check("reason_codes"),
            name="ck_strategy_decisions_reason_codes_json_array",
        ),
        sa.UniqueConstraint(
            "decision_key",
            name="uq_strategy_decisions_decision_key",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_candidate_unique",
        "strategy_decisions",
        ["candidate_id", "strategy_id", "strategy_version"],
        unique=True,
        schema=SCHEMA,
        mssql_where=sa.text("candidate_id IS NOT NULL"),
    )
    op.create_index(
        "ix_strategy_decisions_strategy_decided",
        "strategy_decisions",
        ["strategy_id", "decided_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_candidate",
        "strategy_decisions",
        ["candidate_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_position",
        "strategy_decisions",
        ["position_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_action_decided",
        "strategy_decisions",
        ["action", "decided_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "trade_intents",
        sa.Column("trade_intent_id", uuid_type(), nullable=False),
        sa.Column("decision_id", uuid_type(), nullable=False),
        sa.Column("idempotency_key", code_type(160), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("currency", currency_type(), nullable=False),
        sa.Column("side", code_type(8), nullable=False),
        sa.Column("order_type", code_type(16), nullable=False),
        sa.Column("requested_quantity", sa.BigInteger(), nullable=False),
        sa.Column("limit_price", decimal_type(), nullable=True),
        sa.Column("time_in_force", code_type(16), nullable=False),
        sa.Column("created_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("trade_intent_id", name="pk_trade_intents"),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["trading.strategy_decisions.decision_id"],
            name="fk_trade_intents_decision_id_strategy_decisions",
            ondelete="NO ACTION",
        ),
        named_check_constraint(symbol_check(), name="ck_trade_intents_symbol"),
        named_check_constraint(currency_check(), name="ck_trade_intents_currency"),
        named_check_constraint("side IN ('BUY', 'SELL')", name="ck_trade_intents_side"),
        named_check_constraint(
            "order_type IN ('MARKET', 'LIMIT')",
            name="ck_trade_intents_order_type",
        ),
        named_check_constraint("time_in_force = 'DAY'", name="ck_trade_intents_time_in_force"),
        named_check_constraint(
            "requested_quantity > 0",
            name="ck_trade_intents_quantity_positive",
        ),
        named_check_constraint(
            "(order_type = 'MARKET' AND limit_price IS NULL) "
            "OR (order_type = 'LIMIT' AND limit_price IS NOT NULL AND limit_price > 0)",
            name="ck_trade_intents_limit_price_by_order_type",
        ),
        sa.UniqueConstraint("decision_id", name="uq_trade_intents_decision_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_trade_intents_idempotency_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_trade_intents_created",
        "trade_intents",
        ["created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_trade_intents_symbol_created",
        "trade_intents",
        ["symbol", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_trade_intents_side_created",
        "trade_intents",
        ["side", "created_at"],
        schema=SCHEMA,
    )
