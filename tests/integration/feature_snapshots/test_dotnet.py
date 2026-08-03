import pytest
from sqlalchemy import text

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import (
    DotNetFeatureSnapshotRepository,
    DotNetUnitOfWorkFactory,
)
from auto_trading_v2.application.contracts import FeatureSnapshotCreationOutcome
from auto_trading_v2.application.errors import DuplicateRecordError, TransactionStateError
from auto_trading_v2.application.feature_snapshot_errors import FeatureSnapshotConflictError
from tests.integration.feature_snapshots.helpers import (
    assert_same_snapshot,
    command,
    creation_service,
    new_snapshot,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def test_dotnet_service_create_retry_conflict_and_repository_wiring(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    with dotnet_uow_factory() as unit_of_work:
        assert isinstance(unit_of_work.feature_snapshots, DotNetFeatureSnapshotRepository)

    service = creation_service(dotnet_uow_factory, 200)
    source = command(200)
    created = service.create(source)
    retried = service.create(source)

    assert created.outcome is FeatureSnapshotCreationOutcome.CREATED
    assert retried.outcome is FeatureSnapshotCreationOutcome.ALREADY_EXISTS
    assert_same_snapshot(retried.snapshot, created.snapshot)
    with pytest.raises(FeatureSnapshotConflictError) as captured:
        service.create(command(200, {"close": 999, "payload_marker": "비밀값"}))
    assert "비밀값" not in str(captured.value)


def test_dotnet_commit_visibility_resource_cleanup_and_safe_duplicate(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    pending = new_snapshot(201, feature_values={"payload_marker": "민감값", "value": 1})
    unit_of_work = dotnet_uow_factory()
    with unit_of_work:
        stored = unit_of_work.feature_snapshots.add(pending)
        with mssql_database.engine.connect() as connection:
            invisible_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM trading.feature_snapshots WITH (READPAST) "
                    "WHERE feature_snapshot_id=:identifier"
                ),
                {"identifier": pending.feature_snapshot_id.value},
            ).scalar_one()
        assert invisible_count == 0
        unit_of_work.commit()
    with sqlalchemy_uow_factory() as reader:
        visible = reader.feature_snapshots.get_by_id(pending.feature_snapshot_id)
    assert visible is not None
    assert_same_snapshot(visible, stored)
    assert unit_of_work._connection is None
    with pytest.raises(TransactionStateError):
        _ = unit_of_work.feature_snapshots

    duplicate = new_snapshot(
        201,
        identifier=202,
        feature_values={"payload_marker": "민감값", "value": 1},
    )
    with (
        dotnet_uow_factory() as writer,
        pytest.raises(DuplicateRecordError) as captured,
    ):
        writer.feature_snapshots.add(duplicate)
    assert "민감값" not in str(captured.value)


def test_dotnet_implicit_rollback_is_not_visible(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    rolled_back = new_snapshot(203)
    with dotnet_uow_factory() as unit_of_work:
        unit_of_work.feature_snapshots.add(rolled_back)
    with sqlalchemy_uow_factory() as reader:
        absent = reader.feature_snapshots.get_by_id(rolled_back.feature_snapshot_id)
    assert absent is None
