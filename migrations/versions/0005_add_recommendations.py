"""Add immutable canonical Recommendation storage.

Revision ID: 0005_recommendations
Revises: 0004_feature_snapshots
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.recommendations import create_recommendations_table

revision: str = "0005_recommendations"
down_revision: str | None = "0004_feature_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only trading.recommendations."""

    create_recommendations_table(op)


def downgrade() -> None:
    """Drop only trading.recommendations."""

    op.drop_table("recommendations", schema="trading")
