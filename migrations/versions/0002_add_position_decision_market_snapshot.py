"""Link position strategy decisions to their canonical market snapshot.

Revision ID: 0002_position_snapshot
Revises: 0001_mssql_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.ddl.common import SCHEMA, uuid_type

revision: str = "0002_position_snapshot"
down_revision: str | None = "0001_mssql_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the canonical snapshot source and position decision defenses."""

    op.add_column(
        "strategy_decisions",
        sa.Column("market_snapshot_id", uuid_type(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_strategy_decisions_market_snapshot_id_market_snapshots",
        "strategy_decisions",
        "market_snapshots",
        ["market_snapshot_id"],
        ["market_snapshot_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="NO ACTION",
    )
    op.create_check_constraint(
        op.f("ck_strategy_decisions_candidate_without_snapshot"),
        "strategy_decisions",
        "candidate_id IS NULL OR market_snapshot_id IS NULL",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_strategy_decisions_position_requires_snapshot"),
        "strategy_decisions",
        "position_id IS NULL OR market_snapshot_id IS NOT NULL",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_strategy_decisions_position",
        table_name="strategy_decisions",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_market_snapshot",
        "strategy_decisions",
        ["market_snapshot_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_position_decided",
        "strategy_decisions",
        ["position_id", "decided_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_position_snapshot_unique",
        "strategy_decisions",
        ["position_id", "market_snapshot_id", "strategy_id", "strategy_version"],
        unique=True,
        schema=SCHEMA,
        mssql_where=sa.text("position_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Restore the exact 0001 strategy-decision schema."""

    op.drop_index(
        "ix_strategy_decisions_position_snapshot_unique",
        table_name="strategy_decisions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_strategy_decisions_position_decided",
        table_name="strategy_decisions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_strategy_decisions_market_snapshot",
        table_name="strategy_decisions",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_strategy_decisions_position",
        "strategy_decisions",
        ["position_id"],
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_strategy_decisions_position_requires_snapshot"),
        "strategy_decisions",
        type_="check",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_strategy_decisions_candidate_without_snapshot"),
        "strategy_decisions",
        type_="check",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("fk_strategy_decisions_market_snapshot_id_market_snapshots"),
        "strategy_decisions",
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_column("strategy_decisions", "market_snapshot_id", schema=SCHEMA)
