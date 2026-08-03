"""Add canonical multi-symbol universe and daily feature pipeline.

Revision ID: 0007_multi_symbol_feature_pipeline
Revises: 0006_daily_market_bars
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.ddl.feature_pipeline import create_multi_symbol_feature_pipeline_tables

revision: str = "0007_multi_symbol_feature_pipeline"
down_revision: str | None = "0006_daily_market_bars"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen Alembic bookkeeping and create the three P3 canonical tables."""

    op.drop_constraint(
        "alembic_version_pkc",
        "alembic_version",
        schema="dbo",
        type_="primary",
    )
    op.alter_column(
        "alembic_version",
        "version_num",
        schema="dbo",
        existing_type=sa.String(32),
        type_=sa.String(64),
        existing_nullable=False,
    )
    op.create_primary_key(
        "alembic_version_pkc",
        "alembic_version",
        ["version_num"],
        schema="dbo",
    )
    create_multi_symbol_feature_pipeline_tables(op)


def downgrade() -> None:
    """Drop the P3 tables while retaining compatible Alembic storage width."""

    op.drop_table("daily_feature_pipeline_items", schema="trading")
    op.drop_table("daily_feature_pipeline_runs", schema="trading")
    op.drop_table("universe_snapshots", schema="trading")
