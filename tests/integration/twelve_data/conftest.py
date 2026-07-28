from collections.abc import Iterator

import pytest

from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from tests.integration.daily_market_bars.conftest import mssql_database, sqlalchemy_uow_factory
from tests.integration.persistence.conftest import (
    TemporaryMssqlDatabase,
    temporary_dotnet_uow_factory,
)

__all__ = ["mssql_database", "sqlalchemy_uow_factory"]


@pytest.fixture(scope="session")
def dotnet_uow_factory(
    mssql_database: TemporaryMssqlDatabase,
) -> Iterator[DotNetUnitOfWorkFactory]:
    with temporary_dotnet_uow_factory(mssql_database) as factory:
        yield factory
