"""Canonical paper-position state, position events, and equity snapshots."""

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
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

paper_positions = Table(
    "paper_positions",
    metadata,
    Column("position_id", uuid_type(), primary_key=True),
    Column("strategy_id", uuid_type(), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("currency", currency_type(), nullable=False),
    Column("status", code_type(16), nullable=False),
    Column("quantity", BigInteger(), nullable=False),
    Column("average_cost_price", decimal_type(), nullable=False),
    Column("realized_pnl_amount", decimal_type(), nullable=False),
    Column("opened_at", timestamp_type(), nullable=False),
    Column("closed_at", timestamp_type(), nullable=True),
    Column("version", Integer(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    Column("updated_at", timestamp_type(), nullable=False),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint(currency_check_sql(), name="currency"),
    CheckConstraint("status IN ('OPEN', 'CLOSED')", name="status"),
    CheckConstraint("quantity >= 0", name="quantity_nonnegative"),
    CheckConstraint("average_cost_price >= 0", name="average_cost_nonnegative"),
    CheckConstraint("version > 0", name="version_positive"),
    CheckConstraint(
        "(status = 'OPEN' AND quantity > 0 AND closed_at IS NULL) "
        "OR (status = 'CLOSED' AND quantity = 0 AND closed_at IS NOT NULL)",
        name="status_state",
    ),
    schema=SCHEMA,
)
Index(
    "ix_paper_positions_open_unique",
    paper_positions.c.strategy_id,
    paper_positions.c.symbol,
    paper_positions.c.currency,
    unique=True,
    mssql_where=text("status = 'OPEN'"),
)

position_events = Table(
    "position_events",
    metadata,
    Column("position_event_id", uuid_type(), primary_key=True),
    Column(
        "position_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_positions.position_id",
            name="fk_position_events_position_id_paper_positions",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column(
        "fill_id",
        uuid_type(),
        ForeignKey(
            "trading.paper_fills.fill_id",
            name="fk_position_events_fill_id_paper_fills",
            ondelete="NO ACTION",
        ),
        nullable=False,
    ),
    Column("sequence_no", Integer(), nullable=False),
    Column("event_type", code_type(24), nullable=False),
    Column("quantity_delta", BigInteger(), nullable=False),
    Column("quantity_after", BigInteger(), nullable=False),
    Column("average_cost_after", decimal_type(), nullable=False),
    Column("realized_pnl_delta", decimal_type(), nullable=False),
    Column("realized_pnl_after", decimal_type(), nullable=False),
    Column("occurred_at", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(
        "event_type IN ('OPENED', 'INCREASED', 'REDUCED', 'CLOSED')",
        name="event_type",
    ),
    CheckConstraint("sequence_no > 0", name="sequence_positive"),
    CheckConstraint("quantity_delta <> 0", name="quantity_delta_nonzero"),
    CheckConstraint("quantity_after >= 0", name="quantity_after_nonnegative"),
    CheckConstraint("average_cost_after >= 0", name="average_cost_nonnegative"),
    UniqueConstraint("fill_id", name="uq_position_events_fill_id"),
    UniqueConstraint(
        "position_id",
        "sequence_no",
        name="uq_position_events_position_sequence",
    ),
    schema=SCHEMA,
)
Index(
    "ix_position_events_position_sequence",
    position_events.c.position_id,
    position_events.c.sequence_no,
)
Index("ix_position_events_occurred", position_events.c.occurred_at)
Index("ix_position_events_fill", position_events.c.fill_id)

equity_snapshots = Table(
    "equity_snapshots",
    metadata,
    Column("equity_snapshot_id", uuid_type(), primary_key=True),
    Column("snapshot_key", code_type(160), nullable=False),
    Column("strategy_id", uuid_type(), nullable=False),
    Column("currency", currency_type(), nullable=False),
    Column("cash_amount", decimal_type(), nullable=False),
    Column("market_value_amount", decimal_type(), nullable=False),
    Column("equity_amount", decimal_type(), nullable=False),
    Column("realized_pnl_amount", decimal_type(), nullable=False),
    Column("unrealized_pnl_amount", decimal_type(), nullable=False),
    Column("as_of", timestamp_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(currency_check_sql(), name="currency"),
    CheckConstraint(
        "equity_amount = cash_amount + market_value_amount",
        name="equity_formula",
    ),
    UniqueConstraint("snapshot_key", name="uq_equity_snapshots_snapshot_key"),
    UniqueConstraint(
        "strategy_id",
        "currency",
        "as_of",
        name="uq_equity_snapshots_strategy_currency_as_of",
    ),
    schema=SCHEMA,
)
Index(
    "ix_equity_snapshots_strategy_as_of",
    equity_snapshots.c.strategy_id,
    equity_snapshots.c.as_of,
)
Index("ix_equity_snapshots_as_of", equity_snapshots.c.as_of)
Index(
    "ix_equity_snapshots_currency_as_of",
    equity_snapshots.c.currency,
    equity_snapshots.c.as_of,
)
