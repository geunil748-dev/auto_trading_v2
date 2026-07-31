"""Add canonical multi-symbol universe and daily feature pipeline.

Revision ID: 0007_multi_symbol_feature_pipeline
Revises: 0006_daily_market_bars
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.feature_pipeline import create_multi_symbol_feature_pipeline_tables

revision: str = "0007_multi_symbol_feature_pipeline"
down_revision: str | None = "0006_daily_market_bars"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only the three P3 canonical tables."""

    create_multi_symbol_feature_pipeline_tables(op)


def downgrade() -> None:
    """Drop only the three P3 canonical tables in dependency order."""

    op.drop_table("daily_feature_pipeline_items", schema="trading")
    op.drop_table("daily_feature_pipeline_runs", schema="trading")
    op.drop_table("universe_snapshots", schema="trading")
