"""Add immutable canonical completed daily market bars.

Revision ID: 0006_daily_market_bars
Revises: 0005_recommendations
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.daily_market_bars import create_daily_market_bars_table

revision: str = "0006_daily_market_bars"
down_revision: str | None = "0005_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only trading.daily_market_bars."""

    create_daily_market_bars_table(op)


def downgrade() -> None:
    """Drop only trading.daily_market_bars."""

    op.drop_table("daily_market_bars", schema="trading")
