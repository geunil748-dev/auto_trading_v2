"""Add versioned labels and leakage-safe calibration datasets.

Revision ID: 0010_outcome_labels_calibration_dataset
Revises: 0009_daily_feature_outcomes
"""

from collections.abc import Sequence

from alembic import op

from migrations.ddl.probability_calibration_dataset import (
    create_probability_calibration_dataset_tables,
)

revision: str = "0010_outcome_labels_calibration_dataset"
down_revision: str | None = "0009_daily_feature_outcomes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    create_probability_calibration_dataset_tables(op)


def downgrade() -> None:
    op.drop_table("probability_calibration_dataset_items", schema="trading")
    op.drop_table("probability_calibration_datasets", schema="trading")
    op.drop_table("daily_feature_outcome_labels", schema="trading")
