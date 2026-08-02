"""Add prospective forward outcome observations.

Revision ID: 0009_daily_feature_outcomes
Revises: 0008_daily_feature_scoring
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.feature_outcomes import create_daily_feature_outcome_tables

revision: str = "0009_daily_feature_outcomes"
down_revision: str | None = "0008_daily_feature_scoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only the three additive P4B.1 canonical tables."""

    create_daily_feature_outcome_tables(op)


def downgrade() -> None:
    """Remove only P4B.1 tables in dependency order."""

    op.drop_table("daily_feature_outcome_observation_run_items", schema="trading")
    op.drop_table("daily_feature_outcome_observation_runs", schema="trading")
    op.drop_table("daily_feature_outcomes", schema="trading")
