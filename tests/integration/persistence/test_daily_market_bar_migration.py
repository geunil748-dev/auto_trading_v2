import pytest
from sqlalchemy import inspect

from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
    daily_market_bars,
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


def test_daily_market_bar_revision_round_trip_preserves_prior_13_tables(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    expected_tables = {table.name for table in BUSINESS_TABLES}
    prior_tables = expected_tables - {
        daily_market_bars.name,
        universe_snapshots.name,
        daily_feature_pipeline_runs.name,
        daily_feature_pipeline_items.name,
        daily_feature_scoring_runs.name,
        daily_feature_scoring_items.name,
    }
    assert _revision(mssql_database) == "0008_daily_feature_scoring"
    assert len(prior_tables) == 13
    signature_before = _table_catalog_signature(mssql_database, prior_tables)

    mssql_database.run_downgrade("0005_recommendations")

    assert _revision(mssql_database) == "0005_recommendations"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before

    mssql_database.run_upgrade("head")

    assert _revision(mssql_database) == "0008_daily_feature_scoring"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_check()
