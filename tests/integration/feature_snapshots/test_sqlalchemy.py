import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import feature_snapshots
from auto_trading_v2.application.contracts import FeatureSnapshotCreationOutcome
from auto_trading_v2.application.feature_snapshot_errors import FeatureSnapshotConflictError
from tests.integration.feature_snapshots.helpers import (
    assert_same_snapshot,
    command,
    creation_service,
    new_snapshot,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def test_sqlalchemy_service_create_retry_conflict_and_canonical_round_trip(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    service = creation_service(sqlalchemy_uow_factory, 100)
    source = command(100)

    created = service.create(source)
    retried = service.create(source)

    assert created.outcome is FeatureSnapshotCreationOutcome.CREATED
    assert retried.outcome is FeatureSnapshotCreationOutcome.ALREADY_EXISTS
    assert_same_snapshot(retried.snapshot, created.snapshot)
    assert created.snapshot.snapshot_input.feature_values["close"] == "123.45"
    assert created.snapshot.snapshot_input.provenance[0].source_code == "SOURCE_A"
    with pytest.raises(FeatureSnapshotConflictError) as captured:
        service.create(command(100, {"close": 999, "payload_marker": "비밀값"}))
    assert "비밀값" not in str(captured.value)

    with sqlalchemy_uow_factory() as unit_of_work:
        loaded = unit_of_work.feature_snapshots.get_by_id(created.snapshot.feature_snapshot_id)
    assert loaded is not None
    assert_same_snapshot(loaded, created.snapshot)
    with mssql_database.engine.connect() as connection:
        count = connection.execute(
            select(func.count())
            .select_from(feature_snapshots)
            .where(feature_snapshots.c.snapshot_key == created.snapshot.snapshot_key)
        ).scalar_one()
    assert count == 1


def test_sqlalchemy_repository_commit_and_implicit_rollback(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    committed = new_snapshot(101)
    with sqlalchemy_uow_factory() as unit_of_work:
        stored = unit_of_work.feature_snapshots.add(committed)
        assert unit_of_work.feature_snapshots.get_by_snapshot_key(stored.snapshot_key) is not None
        unit_of_work.commit()
    with sqlalchemy_uow_factory() as unit_of_work:
        visible = unit_of_work.feature_snapshots.get_by_id(committed.feature_snapshot_id)
    assert visible is not None

    rolled_back = new_snapshot(102)
    with sqlalchemy_uow_factory() as unit_of_work:
        unit_of_work.feature_snapshots.add(rolled_back)
    with sqlalchemy_uow_factory() as unit_of_work:
        absent = unit_of_work.feature_snapshots.get_by_id(rolled_back.feature_snapshot_id)
    assert absent is None
