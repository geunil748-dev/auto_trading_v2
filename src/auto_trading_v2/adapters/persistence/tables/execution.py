"""Canonical paper-order state and immutable fill tables."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
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
    non_empty_check_sql,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

paper_orders = Table(
    "paper_orders",
    metadata,
    Column("order_id", uuid_type(), primary_key=True),
    Column(
        "trade_intent_id",
        uuid_type(),
        ForeignKey(
            "trading.trade_intents.trade_intent_id",
            name="fk_paper_orders_trade_intent_id_trade_intents",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column("client_order_id", uuid_type(), nullable=False),
    Column("broker_code", code_type(32), nullable=False),
    Column("broker_order_ref", code_type(160), nullable=True),
    Column("status", code_type(24), nullable=False),
    Column("rejection_code", code_type(64), nullable=True),
    Column("submitted_at", timestamp_type(), nullable=False),
    Column("accepted_at", timestamp_type(), nullable=True),
    Column("closed_at", timestamp_type(), nullable=True),
    Column("version", Integer(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    Column("updated_at", timestamp_type(), nullable=False),
    CheckConstraint(
        "status IN ('CREATED', 'ACCEPTED', 'PARTIALLY_FILLED', "
        "'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')",
        name="status",
    ),
    CheckConstraint(non_empty_check_sql("broker_code"), name="broker_code_nonempty"),
    CheckConstraint("version > 0", name="version_positive"),
    CheckConstraint(
        "(status IN ('CREATED', 'ACCEPTED', 'PARTIALLY_FILLED') AND closed_at IS NULL) "
        "OR (status IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED') "
        "AND closed_at IS NOT NULL)",
        name="status_closed_at",
    ),
    UniqueConstraint("trade_intent_id", name="uq_paper_orders_trade_intent_id"),
    UniqueConstraint("client_order_id", name="uq_paper_orders_client_order_id"),
    schema=SCHEMA,
)
Index(
    "ix_paper_orders_broker_ref_unique",
    paper_orders.c.broker_code,
    paper_orders.c.broker_order_ref,
    unique=True,
    mssql_where=text("broker_order_ref IS NOT NULL"),
)
Index(
    "ix_paper_orders_status_updated",
    paper_orders.c.status,
    paper_orders.c.updated_at,
)
Index(
    "ix_paper_orders_broker_submitted",
    paper_orders.c.broker_code,
    paper_orders.c.submitted_at,
)
Index("ix_paper_orders_submitted", paper_orders.c.submitted_at)

paper_fills = Table(
    "paper_fills",
    metadata,
    Column("fill_id", uuid_type(), primary_key=True),
    Column(
        "order_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_orders.order_id",
            name="fk_paper_fills_order_id_paper_orders",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column("execution_key", code_type(160), nullable=False),
    Column("fill_sequence", Integer(), nullable=False),
    Column("quantity", BigInteger(), nullable=False),
    Column("price", decimal_type(), nullable=False),
    Column("fee_amount", decimal_type(), nullable=False),
    Column("fee_currency", currency_type(), nullable=False),
    Column("executed_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(currency_check_sql("fee_currency"), name="fee_currency"),
    CheckConstraint("fill_sequence > 0", name="sequence_positive"),
    CheckConstraint("quantity > 0", name="quantity_positive"),
    CheckConstraint("price > 0", name="price_positive"),
    CheckConstraint("fee_amount >= 0", name="fee_nonnegative"),
    UniqueConstraint("execution_key", name="uq_paper_fills_execution_key"),
    UniqueConstraint(
        "order_id",
        "fill_sequence",
        name="uq_paper_fills_order_sequence",
    ),
    schema=SCHEMA,
)
Index(
    "ix_paper_fills_order_sequence",
    paper_fills.c.order_id,
    paper_fills.c.fill_sequence,
)
Index("ix_paper_fills_executed", paper_fills.c.executed_at)
Index(
    "ix_paper_fills_order_executed",
    paper_fills.c.order_id,
    paper_fills.c.executed_at,
)
