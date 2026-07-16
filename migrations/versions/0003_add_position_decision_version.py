"""Pin position decisions to the canonical PositionEvent version.

Revision ID: 0003_position_decision_version
Revises: 0002_position_snapshot
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.ddl.common import SCHEMA

revision: str = "0003_position_decision_version"
down_revision: str | None = "0002_position_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a version pin without guessing values for existing position decisions."""

    op.execute(
        "IF EXISTS ("
        "SELECT 1 FROM trading.strategy_decisions WHERE position_id IS NOT NULL"
        ") THROW 51000, "
        "'0003 migration blocked: existing position decisions require explicit backfill', 1"
    )
    op.add_column(
        "strategy_decisions",
        sa.Column("position_version", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_strategy_decisions_candidate_without_position_version"),
        "strategy_decisions",
        "candidate_id IS NULL OR position_version IS NULL",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_strategy_decisions_position_requires_version"),
        "strategy_decisions",
        "position_id IS NULL OR position_version IS NOT NULL",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_strategy_decisions_position_version_positive"),
        "strategy_decisions",
        "position_version IS NULL OR position_version > 0",
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_strategy_decisions_position_version_position_events",
        "strategy_decisions",
        "position_events",
        ["position_id", "position_version"],
        ["position_id", "sequence_no"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="NO ACTION",
    )
    op.create_index(
        "ix_strategy_decisions_position_version",
        "strategy_decisions",
        ["position_id", "position_version"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Restore the exact 0002 position-decision schema."""

    op.drop_index(
        "ix_strategy_decisions_position_version",
        table_name="strategy_decisions",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("fk_strategy_decisions_position_version_position_events"),
        "strategy_decisions",
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_strategy_decisions_position_version_positive"),
        "strategy_decisions",
        type_="check",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_strategy_decisions_position_requires_version"),
        "strategy_decisions",
        type_="check",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_strategy_decisions_candidate_without_position_version"),
        "strategy_decisions",
        type_="check",
        schema=SCHEMA,
    )
    op.drop_column("strategy_decisions", "position_version", schema=SCHEMA)
