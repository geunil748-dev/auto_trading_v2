"""Frozen initial DDL for position state, events, and equity snapshots."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    currency_check,
    currency_type,
    decimal_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def create_portfolio_tables(op: Operations, *, positions_only: bool) -> None:
    """Create positions first, then dependent event and equity tables."""

    if positions_only:
        _create_positions(op)
        return
    _create_position_events(op)
    _create_equity_snapshots(op)


def _create_positions(op: Operations) -> None:
    op.create_table(
        "paper_positions",
        sa.Column("position_id", uuid_type(), nullable=False),
        sa.Column("strategy_id", uuid_type(), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("currency", currency_type(), nullable=False),
        sa.Column("status", code_type(16), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("average_cost_price", decimal_type(), nullable=False),
        sa.Column("realized_pnl_amount", decimal_type(), nullable=False),
        sa.Column("opened_at", timestamp_type(), nullable=False),
        sa.Column("closed_at", timestamp_type(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.Column("updated_at", timestamp_type(), nullable=False),
        sa.PrimaryKeyConstraint("position_id", name="pk_paper_positions"),
        named_check_constraint(symbol_check(), name="ck_paper_positions_symbol"),
        named_check_constraint(currency_check(), name="ck_paper_positions_currency"),
        named_check_constraint("status IN ('OPEN', 'CLOSED')", name="ck_paper_positions_status"),
        named_check_constraint("quantity >= 0", name="ck_paper_positions_quantity_nonnegative"),
        named_check_constraint(
            "average_cost_price >= 0",
            name="ck_paper_positions_average_cost_nonnegative",
        ),
        named_check_constraint("version > 0", name="ck_paper_positions_version_positive"),
        named_check_constraint(
            "(status = 'OPEN' AND quantity > 0 AND closed_at IS NULL) "
            "OR (status = 'CLOSED' AND quantity = 0 AND closed_at IS NOT NULL)",
            name="ck_paper_positions_status_state",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_paper_positions_open_unique",
        "paper_positions",
        ["strategy_id", "symbol", "currency"],
        unique=True,
        schema=SCHEMA,
        mssql_where=sa.text("status = 'OPEN'"),
    )


def _create_position_events(op: Operations) -> None:
    op.create_table(
        "position_events",
        sa.Column("position_event_id", uuid_type(), nullable=False),
        sa.Column("position_id", uuid_type(), nullable=False),
        sa.Column("fill_id", uuid_type(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_type", code_type(24), nullable=False),
        sa.Column("quantity_delta", sa.BigInteger(), nullable=False),
        sa.Column("quantity_after", sa.BigInteger(), nullable=False),
        sa.Column("average_cost_after", decimal_type(), nullable=False),
        sa.Column("realized_pnl_delta", decimal_type(), nullable=False),
        sa.Column("realized_pnl_after", decimal_type(), nullable=False),
        sa.Column("occurred_at", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("position_event_id", name="pk_position_events"),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["trading.paper_positions.position_id"],
            name="fk_position_events_position_id_paper_positions",
            ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["fill_id"],
            ["trading.paper_fills.fill_id"],
            name="fk_position_events_fill_id_paper_fills",
            ondelete="NO ACTION",
        ),
        named_check_constraint(
            "event_type IN ('OPENED', 'INCREASED', 'REDUCED', 'CLOSED')",
            name="ck_position_events_event_type",
        ),
        named_check_constraint("sequence_no > 0", name="ck_position_events_sequence_positive"),
        named_check_constraint(
            "quantity_delta <> 0",
            name="ck_position_events_quantity_delta_nonzero",
        ),
        named_check_constraint(
            "quantity_after >= 0",
            name="ck_position_events_quantity_after_nonnegative",
        ),
        named_check_constraint(
            "average_cost_after >= 0",
            name="ck_position_events_average_cost_nonnegative",
        ),
        sa.UniqueConstraint("fill_id", name="uq_position_events_fill_id"),
        sa.UniqueConstraint(
            "position_id",
            "sequence_no",
            name="uq_position_events_position_sequence",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_position_events_position_sequence",
        "position_events",
        ["position_id", "sequence_no"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_position_events_occurred",
        "position_events",
        ["occurred_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_position_events_fill",
        "position_events",
        ["fill_id"],
        schema=SCHEMA,
    )


def _create_equity_snapshots(op: Operations) -> None:
    op.create_table(
        "equity_snapshots",
        sa.Column("equity_snapshot_id", uuid_type(), nullable=False),
        sa.Column("snapshot_key", code_type(160), nullable=False),
        sa.Column("strategy_id", uuid_type(), nullable=False),
        sa.Column("currency", currency_type(), nullable=False),
        sa.Column("cash_amount", decimal_type(), nullable=False),
        sa.Column("market_value_amount", decimal_type(), nullable=False),
        sa.Column("equity_amount", decimal_type(), nullable=False),
        sa.Column("realized_pnl_amount", decimal_type(), nullable=False),
        sa.Column("unrealized_pnl_amount", decimal_type(), nullable=False),
        sa.Column("as_of", timestamp_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("equity_snapshot_id", name="pk_equity_snapshots"),
        named_check_constraint(currency_check(), name="ck_equity_snapshots_currency"),
        named_check_constraint(
            "equity_amount = cash_amount + market_value_amount",
            name="ck_equity_snapshots_equity_formula",
        ),
        sa.UniqueConstraint("snapshot_key", name="uq_equity_snapshots_snapshot_key"),
        sa.UniqueConstraint(
            "strategy_id",
            "currency",
            "as_of",
            name="uq_equity_snapshots_strategy_currency_as_of",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_equity_snapshots_strategy_as_of",
        "equity_snapshots",
        ["strategy_id", "as_of"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_equity_snapshots_as_of",
        "equity_snapshots",
        ["as_of"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_equity_snapshots_currency_as_of",
        "equity_snapshots",
        ["currency", "as_of"],
        schema=SCHEMA,
    )
