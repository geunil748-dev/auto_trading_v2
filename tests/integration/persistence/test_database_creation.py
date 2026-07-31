import pytest
from sqlalchemy import inspect, text

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES
from auto_trading_v2.config import MssqlAdministrationTransport

pytestmark = pytest.mark.integration


def test_temporary_database_is_v2_prefixed_and_connected(mssql_database: object) -> None:
    database = mssql_database
    assert database.name.startswith("auto_trading_v2_test_")
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT DB_NAME()")).scalar_one() == database.name
        if database.administration_transport is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY:
            assert (
                connection.exec_driver_sql(
                    "SELECT CONNECTIONPROPERTY('net_transport')"
                ).scalar_one()
                == "Shared memory"
            )


def test_server_meets_supported_capabilities(mssql_database: object) -> None:
    info = mssql_database.server_info
    assert info.product_major_version >= 13
    assert info.compatibility_level is not None
    assert info.compatibility_level >= 130
    assert info.binary_collation_available
    assert "synapse" not in info.edition.casefold()


def test_trading_schema_and_all_business_tables_exist(mssql_database: object) -> None:
    inspector = inspect(mssql_database.engine)
    assert inspector.has_schema("trading")
    assert len(inspector.get_table_names(schema="trading")) == len(BUSINESS_TABLES)
