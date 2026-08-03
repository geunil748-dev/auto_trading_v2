import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from tests.integration.recommendations.helpers import (
    assert_same_recommendation,
    command,
    creation_service,
    persist_snapshot,
)

pytestmark = pytest.mark.integration


def test_dotnet_write_sqlalchemy_read_and_sqlalchemy_write_dotnet_read(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    dotnet_snapshot = persist_snapshot(dotnet_uow_factory, 121)
    dotnet_written = (
        creation_service(dotnet_uow_factory, dotnet_snapshot, 121)
        .create(command(dotnet_snapshot, 121))
        .recommendation
    )

    with sqlalchemy_uow_factory() as reader:
        sqlalchemy_read = reader.recommendations.get_by_id(dotnet_written.recommendation_id)
    assert sqlalchemy_read is not None
    assert_same_recommendation(sqlalchemy_read, dotnet_written)

    sqlalchemy_snapshot = persist_snapshot(sqlalchemy_uow_factory, 122)
    sqlalchemy_written = (
        creation_service(sqlalchemy_uow_factory, sqlalchemy_snapshot, 122)
        .create(command(sqlalchemy_snapshot, 122))
        .recommendation
    )

    with dotnet_uow_factory() as reader:
        dotnet_read = reader.recommendations.get_by_id(sqlalchemy_written.recommendation_id)
    assert dotnet_read is not None
    assert_same_recommendation(dotnet_read, sqlalchemy_written)
