"""Create the canonical Microsoft SQL Server schema.

Revision ID: 0001_mssql_schema
Revises: None
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl import (
    create_execution_tables,
    create_market_tables,
    create_portfolio_tables,
    create_strategy_tables,
    create_trading_events,
)

revision: str = "0001_mssql_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_ORDER = (
    "trading_events",
    "equity_snapshots",
    "position_events",
    "paper_fills",
    "paper_orders",
    "trade_intents",
    "strategy_decisions",
    "paper_positions",
    "filter_evaluations",
    "candidates",
    "market_snapshots",
)


def upgrade() -> None:
    """Create the trading schema and all canonical tables in dependency order."""

    op.execute("IF SCHEMA_ID(N'trading') IS NULL EXEC(N'CREATE SCHEMA [trading]')")
    create_market_tables(op)
    create_portfolio_tables(op, positions_only=True)
    create_strategy_tables(op)
    create_execution_tables(op)
    create_portfolio_tables(op, positions_only=False)
    create_trading_events(op)


def downgrade() -> None:
    """Drop only V2 business tables and remove an empty trading schema."""

    for table_name in _DROP_ORDER:
        op.drop_table(table_name, schema="trading")
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE schema_id = SCHEMA_ID(N'trading')) "
        "EXEC(N'DROP SCHEMA [trading]')"
    )
