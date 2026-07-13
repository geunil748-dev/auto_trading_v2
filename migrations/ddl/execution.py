"""Frozen initial DDL for paper orders and fills."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    currency_check,
    currency_type,
    decimal_type,
    timestamp_type,
    uuid_type,
)


def create_execution_tables(op: Operations) -> None:
    """Create canonical paper order state and immutable fill tables."""

    op.create_table(
        "paper_orders",
        sa.Column("order_id", uuid_type(), nullable=False),
        sa.Column("trade_intent_id", uuid_type(), nullable=False),
        sa.Column("client_order_id", uuid_type(), nullable=False),
        sa.Column("broker_code", code_type(32), nullable=False),
        sa.Column("broker_order_ref", code_type(160), nullable=True),
        sa.Column("status", code_type(24), nullable=False),
        sa.Column("rejection_code", code_type(64), nullable=True),
        sa.Column("submitted_at", timestamp_type(), nullable=False),
        sa.Column("accepted_at", timestamp_type(), nullable=True),
        sa.Column("closed_at", timestamp_type(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.Column("updated_at", timestamp_type(), nullable=False),
        sa.PrimaryKeyConstraint("order_id", name="pk_paper_orders"),
        sa.ForeignKeyConstraint(
            ["trade_intent_id"],
            ["trading.trade_intents.trade_intent_id"],
            name="fk_paper_orders_trade_intent_id_trade_intents",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'ACCEPTED', 'PARTIALLY_FILLED', "
            "'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')",
            name="ck_paper_orders_status",
        ),
        sa.CheckConstraint(
            "DATALENGTH(LTRIM(RTRIM(broker_code))) > 0",
            name="ck_paper_orders_broker_code_nonempty",
        ),
        sa.CheckConstraint("version > 0", name="ck_paper_orders_version_positive"),
        sa.CheckConstraint(
            "(status IN ('CREATED', 'ACCEPTED', 'PARTIALLY_FILLED') AND closed_at IS NULL) "
            "OR (status IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED') "
            "AND closed_at IS NOT NULL)",
            name="ck_paper_orders_status_closed_at",
        ),
        sa.UniqueConstraint("trade_intent_id", name="uq_paper_orders_trade_intent_id"),
        sa.UniqueConstraint("client_order_id", name="uq_paper_orders_client_order_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_orders_broker_ref_unique",
        "paper_orders",
        ["broker_code", "broker_order_ref"],
        unique=True,
        schema=SCHEMA,
        mssql_where=sa.text("broker_order_ref IS NOT NULL"),
    )
    op.create_index(
        "ix_paper_orders_status_updated",
        "paper_orders",
        ["status", "updated_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_orders_broker_submitted",
        "paper_orders",
        ["broker_code", "submitted_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_orders_submitted",
        "paper_orders",
        ["submitted_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "paper_fills",
        sa.Column("fill_id", uuid_type(), nullable=False),
        sa.Column("order_id", uuid_type(), nullable=False),
        sa.Column("execution_key", code_type(160), nullable=False),
        sa.Column("fill_sequence", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("price", decimal_type(), nullable=False),
        sa.Column("fee_amount", decimal_type(), nullable=False),
        sa.Column("fee_currency", currency_type(), nullable=False),
        sa.Column("executed_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("fill_id", name="pk_paper_fills"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["trading.paper_orders.order_id"],
            name="fk_paper_fills_order_id_paper_orders",
            ondelete="NO ACTION",
        ),
        sa.CheckConstraint(
            currency_check("fee_currency"),
            name="ck_paper_fills_fee_currency",
        ),
        sa.CheckConstraint("fill_sequence > 0", name="ck_paper_fills_sequence_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_paper_fills_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_paper_fills_price_positive"),
        sa.CheckConstraint("fee_amount >= 0", name="ck_paper_fills_fee_nonnegative"),
        sa.UniqueConstraint("execution_key", name="uq_paper_fills_execution_key"),
        sa.UniqueConstraint(
            "order_id",
            "fill_sequence",
            name="uq_paper_fills_order_sequence",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_fills_order_sequence",
        "paper_fills",
        ["order_id", "fill_sequence"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_fills_executed",
        "paper_fills",
        ["executed_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_fills_order_executed",
        "paper_fills",
        ["order_id", "executed_at"],
        schema=SCHEMA,
    )
