import pytest
from sqlalchemy import inspect, text

from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    daily_feature_outcome_observation_run_items,
    daily_feature_outcome_observation_runs,
    daily_feature_outcomes,
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
    universe_snapshots,
)
from tests.integration.persistence.catalog_helpers import (
    revision as _revision,
)
from tests.integration.persistence.catalog_helpers import (
    table_catalog_signature as _table_catalog_signature,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def _version_column_length(database: TemporaryMssqlDatabase) -> int:
    with database.engine.connect() as connection:
        return int(
            connection.execute(
                text(
                    "SELECT c.max_length FROM sys.columns c "
                    "JOIN sys.tables t ON c.object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "WHERE s.name = 'dbo' AND t.name = 'alembic_version' "
                    "AND c.name = 'version_num'"
                )
            ).scalar_one()
        )


def test_0007_round_trip_preserves_all_prior_fourteen_tables(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    head = {table.name for table in BUSINESS_TABLES}
    downstream = {
        daily_feature_scoring_runs.name,
        daily_feature_scoring_items.name,
        daily_feature_outcomes.name,
        daily_feature_outcome_observation_runs.name,
        daily_feature_outcome_observation_run_items.name,
        "daily_feature_outcome_labels",
        "probability_calibration_datasets",
        "probability_calibration_dataset_items",
    }
    expected = head - downstream
    added = {
        universe_snapshots.name,
        daily_feature_pipeline_runs.name,
        daily_feature_pipeline_items.name,
    }
    prior = expected - added
    assert len(expected) == 17
    assert len(prior) == 14
    assert _version_column_length(mssql_database) == 64
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    signature = _table_catalog_signature(mssql_database, prior)

    mssql_database.run_downgrade("0006_daily_market_bars")

    assert _revision(mssql_database) == "0006_daily_market_bars"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior
    assert _table_catalog_signature(mssql_database, prior) == signature

    mssql_database.run_upgrade("0007_multi_symbol_feature_pipeline")

    assert _revision(mssql_database) == "0007_multi_symbol_feature_pipeline"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected
    assert _table_catalog_signature(mssql_database, prior) == signature
    mssql_database.run_upgrade("head")
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == head
    mssql_database.run_check()
