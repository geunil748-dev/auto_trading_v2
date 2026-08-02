"""Add canonical daily feature scoring runs and items.

Revision ID: 0008_daily_feature_scoring
Revises: 0007_multi_symbol_feature_pipeline
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.feature_scoring import create_daily_feature_scoring_tables

revision: str = "0008_daily_feature_scoring"
down_revision: str | None = "0007_multi_symbol_feature_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only the two additive P4A canonical tables."""

    create_daily_feature_scoring_tables(op)


def downgrade() -> None:
    """Remove only P4A items and runs in dependency order."""

    op.drop_table("daily_feature_scoring_items", schema="trading")
    op.drop_table("daily_feature_scoring_runs", schema="trading")
