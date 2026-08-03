"""Create the three additive P4B.2A canonical tables."""

from alembic.operations import Operations

from migrations.ddl.outcome_labels import create_daily_feature_outcome_labels_table
from migrations.ddl.probability_calibration_dataset_items import (
    create_probability_calibration_dataset_items_table,
)
from migrations.ddl.probability_calibration_datasets import (
    create_probability_calibration_datasets_table,
)


def create_probability_calibration_dataset_tables(op: Operations) -> None:
    create_daily_feature_outcome_labels_table(op)
    create_probability_calibration_datasets_table(op)
    create_probability_calibration_dataset_items_table(op)
