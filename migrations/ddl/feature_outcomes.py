"""Additive DDL orchestration for the three P4B.1 canonical tables."""

from alembic.operations import Operations

from migrations.ddl.feature_outcome_records import create_daily_feature_outcomes_table
from migrations.ddl.feature_outcome_run_items import (
    create_daily_feature_outcome_observation_run_items_table,
)
from migrations.ddl.feature_outcome_runs import (
    create_daily_feature_outcome_observation_runs_table,
)


def create_daily_feature_outcome_tables(op: Operations) -> None:
    """Create only the three P4B.1 tables in dependency order."""

    create_daily_feature_outcomes_table(op)
    create_daily_feature_outcome_observation_runs_table(op)
    create_daily_feature_outcome_observation_run_items_table(op)
