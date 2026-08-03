"""Add immutable Point-in-Time FeatureSnapshot storage.

Revision ID: 0004_feature_snapshots
Revises: 0003_position_decision_version
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.features import create_feature_snapshot_table

revision: str = "0004_feature_snapshots"
down_revision: str | None = "0003_position_decision_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only trading.feature_snapshots."""

    create_feature_snapshot_table(op)


def downgrade() -> None:
    """Drop only trading.feature_snapshots."""

    op.drop_table("feature_snapshots", schema="trading")
