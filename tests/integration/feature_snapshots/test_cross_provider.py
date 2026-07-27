import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.contracts import FeatureSnapshotCreationOutcome
from tests.integration.feature_snapshots.helpers import (
    assert_same_snapshot,
    command,
    creation_service,
)

pytestmark = pytest.mark.integration


def test_dotnet_and_sqlalchemy_read_each_others_canonical_rows(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    dotnet_created = creation_service(dotnet_uow_factory, 300).create(command(300))
    assert dotnet_created.outcome is FeatureSnapshotCreationOutcome.CREATED
    with sqlalchemy_uow_factory() as sqlalchemy_reader:
        sqlalchemy_loaded = sqlalchemy_reader.feature_snapshots.get_by_id(
            dotnet_created.snapshot.feature_snapshot_id
        )
    assert sqlalchemy_loaded is not None
    assert_same_snapshot(sqlalchemy_loaded, dotnet_created.snapshot)

    sqlalchemy_created = creation_service(sqlalchemy_uow_factory, 301).create(command(301))
    assert sqlalchemy_created.outcome is FeatureSnapshotCreationOutcome.CREATED
    with dotnet_uow_factory() as dotnet_reader:
        dotnet_loaded = dotnet_reader.feature_snapshots.get_by_id(
            sqlalchemy_created.snapshot.feature_snapshot_id
        )
    assert dotnet_loaded is not None
    assert_same_snapshot(dotnet_loaded, sqlalchemy_created.snapshot)
