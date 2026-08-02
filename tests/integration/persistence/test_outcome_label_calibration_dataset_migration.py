import pytest
from sqlalchemy import inspect

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES
from tests.integration.persistence.catalog_helpers import revision as _revision
from tests.integration.persistence.catalog_helpers import (
    table_catalog_signature as _table_catalog_signature,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration

NEW_TABLES = {
    "daily_feature_outcome_labels",
    "probability_calibration_datasets",
    "probability_calibration_dataset_items",
}


def test_0010_round_trip_preserves_the_prior_twenty_two_table_catalog(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    expected = {table.name for table in BUSINESS_TABLES}
    prior = expected - NEW_TABLES

    assert len(expected) == 25
    assert len(prior) == 22
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected
    signature = _table_catalog_signature(mssql_database, prior)

    mssql_database.run_downgrade("0009_daily_feature_outcomes")

    assert _revision(mssql_database) == "0009_daily_feature_outcomes"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior
    assert _table_catalog_signature(mssql_database, prior) == signature

    mssql_database.run_upgrade("head")

    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected
    assert _table_catalog_signature(mssql_database, prior) == signature
    mssql_database.run_check()
