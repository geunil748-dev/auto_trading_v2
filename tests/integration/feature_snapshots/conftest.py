from dataclasses import replace

import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import (
    DotNetConnectionFactory,
    DotNetUnitOfWorkFactory,
)
from auto_trading_v2.config.dotnet_database import load_dotnet_database_settings
from tests.integration.persistence.conftest import (
    TemporaryMssqlDatabase,
    mssql_database,
)

__all__ = ["mssql_database"]


@pytest.fixture(scope="session")
def sqlalchemy_uow_factory(
    mssql_database: TemporaryMssqlDatabase,
) -> SqlAlchemyUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(mssql_database.engine)


@pytest.fixture(scope="session")
def dotnet_uow_factory(
    mssql_database: TemporaryMssqlDatabase,
) -> DotNetUnitOfWorkFactory:
    assert mssql_database.name.startswith("auto_trading_v2_test_")
    runtime_settings = load_dotnet_database_settings()
    test_settings = replace(
        runtime_settings,
        environment="test",
        database=mssql_database.name,
    )
    return DotNetUnitOfWorkFactory(DotNetConnectionFactory(test_settings))
