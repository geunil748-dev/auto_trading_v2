import pytest
from sqlalchemy import inspect

from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
    daily_market_bars,
    universe_snapshots,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.persistence.test_migrations import (
    _revision,
    _table_catalog_signature,
)

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
    }
    assert _revision(mssql_database) == "0007_multi_symbol_feature_pipeline"
    assert len(prior_tables) == 13
    signature_before = _table_catalog_signature(mssql_database, prior_tables)

    mssql_database.run_downgrade("0005_recommendations")

    assert _revision(mssql_database) == "0005_recommendations"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before

    mssql_database.run_upgrade("head")

    assert _revision(mssql_database) == "0007_multi_symbol_feature_pipeline"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_check()
