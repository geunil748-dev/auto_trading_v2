import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from tests.integration.daily_market_bars.helpers import (
    assert_same_bar,
    command,
    creation_service,
)

pytestmark = pytest.mark.integration


def test_dotnet_write_sqlalchemy_read_and_sqlalchemy_write_dotnet_read(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    dotnet_written = creation_service(dotnet_uow_factory, 231001).create(command(231, 0)).bar
    with sqlalchemy_uow_factory() as reader:
        sqlalchemy_read = reader.daily_market_bars.get_by_id(dotnet_written.daily_market_bar_id)
    assert sqlalchemy_read is not None
    assert_same_bar(sqlalchemy_read, dotnet_written)

    sqlalchemy_written = (
        creation_service(sqlalchemy_uow_factory, 232001).create(command(232, 0)).bar
    )
    with dotnet_uow_factory() as reader:
        dotnet_read = reader.daily_market_bars.get_by_id(sqlalchemy_written.daily_market_bar_id)
    assert dotnet_read is not None
    assert_same_bar(dotnet_read, sqlalchemy_written)
