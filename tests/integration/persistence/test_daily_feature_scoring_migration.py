import pytest
from sqlalchemy import inspect

from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    daily_feature_outcome_observation_run_items,
    daily_feature_outcome_observation_runs,
    daily_feature_outcomes,
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
)
from tests.integration.persistence.catalog_helpers import (
    revision as _revision,
)
from tests.integration.persistence.catalog_helpers import (
    table_catalog_signature as _table_catalog_signature,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def test_0008_round_trip_preserves_all_prior_seventeen_tables(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    head = {table.name for table in BUSINESS_TABLES}
    downstream = {
        daily_feature_outcomes.name,
        daily_feature_outcome_observation_runs.name,
        daily_feature_outcome_observation_run_items.name,
    }
    expected = head - downstream
    added = {daily_feature_scoring_runs.name, daily_feature_scoring_items.name}
    prior = expected - added

    assert len(expected) == 19
    assert len(prior) == 17
    assert _revision(mssql_database) == "0009_daily_feature_outcomes"
    mssql_database.run_downgrade("0008_daily_feature_scoring")
    assert _revision(mssql_database) == "0008_daily_feature_scoring"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected
    signature = _table_catalog_signature(mssql_database, prior)

    mssql_database.run_downgrade("0007_multi_symbol_feature_pipeline")

    assert _revision(mssql_database) == "0007_multi_symbol_feature_pipeline"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior
    assert _table_catalog_signature(mssql_database, prior) == signature

    mssql_database.run_upgrade("head")

    assert _revision(mssql_database) == "0009_daily_feature_outcomes"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == head
    assert _table_catalog_signature(mssql_database, prior) == signature
    mssql_database.run_check()
