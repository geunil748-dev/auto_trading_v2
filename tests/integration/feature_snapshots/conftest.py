from collections.abc import Iterator

import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from tests.integration.persistence.conftest import (
    TemporaryMssqlDatabase,
    mssql_database,
    temporary_dotnet_uow_factory,
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
) -> Iterator[DotNetUnitOfWorkFactory]:
    assert mssql_database.name.startswith("auto_trading_v2_test_")
    with temporary_dotnet_uow_factory(mssql_database) as factory:
        yield factory
