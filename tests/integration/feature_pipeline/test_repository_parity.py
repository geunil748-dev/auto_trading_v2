import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.contracts.universes import UniverseSnapshotCreationOutcome
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.universe_errors import UniverseSnapshotConflictError
from tests.integration.feature_pipeline.helpers import (
    aggregate,
    universe_command,
    universe_service,
)
from tests.integration.feature_snapshots.helpers import new_snapshot

pytestmark = pytest.mark.integration


def test_universe_create_read_retry_conflict_and_cross_provider_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    sql_service = universe_service(sqlalchemy_uow_factory, 701001)
    sql_created = sql_service.create(universe_command(701, "MSFT", "AAPL"))
    assert sql_created.outcome is UniverseSnapshotCreationOutcome.CREATED
    assert sql_service.create(universe_command(701, "AAPL", "MSFT")).outcome is (
        UniverseSnapshotCreationOutcome.ALREADY_EXISTS
    )
    with dotnet_uow_factory() as reader:
        dotnet_read = reader.universe_snapshots.get_by_id(sql_created.snapshot.universe_snapshot_id)
    assert dotnet_read == sql_created.snapshot

    dotnet_service = universe_service(dotnet_uow_factory, 702001)
    dotnet_created = dotnet_service.create(universe_command(702, "NVDA"))
    with sqlalchemy_uow_factory() as reader:
        sqlalchemy_read = reader.universe_snapshots.get_by_id(
            dotnet_created.snapshot.universe_snapshot_id
        )
    assert sqlalchemy_read == dotnet_created.snapshot
    with pytest.raises(UniverseSnapshotConflictError):
        sql_service.create(universe_command(701, "NVDA"))


def test_pipeline_run_items_cross_provider_order_nullability_rollback_and_unique(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    universe_one = (
        universe_service(sqlalchemy_uow_factory, 711001)
        .create(universe_command(711, "AAPL", "MSFT"))
        .snapshot
    )
    feature_one = new_snapshot(711, identifier=711001)
    with sqlalchemy_uow_factory() as unit_of_work:
        stored_feature_one = unit_of_work.feature_snapshots.add(feature_one)
        unit_of_work.commit()
    first = aggregate(universe_one, stored_feature_one.feature_snapshot_id, 711)
    with sqlalchemy_uow_factory() as unit_of_work:
        sql_written = unit_of_work.daily_feature_pipeline_runs.add_run_with_items(first)
        unit_of_work.commit()
    with dotnet_uow_factory() as reader:
        dotnet_read = reader.daily_feature_pipeline_runs.get_run_with_items(
            sql_written.run.daily_feature_pipeline_run_id
        )
    assert dotnet_read == sql_written
    assert [item.ordinal for item in dotnet_read.items] == [1, 2]
    assert dotnet_read.items[0].feature_snapshot_id is not None
    assert dotnet_read.items[1].feature_snapshot_id is None

    universe_two = (
        universe_service(dotnet_uow_factory, 712001)
        .create(universe_command(712, "AAPL", "MSFT"))
        .snapshot
    )
    feature_two = new_snapshot(712, identifier=712001)
    with dotnet_uow_factory() as unit_of_work:
        stored_feature_two = unit_of_work.feature_snapshots.add(feature_two)
        unit_of_work.commit()
    second = aggregate(universe_two, stored_feature_two.feature_snapshot_id, 712)
    with dotnet_uow_factory() as unit_of_work:
        dotnet_written = unit_of_work.daily_feature_pipeline_runs.add_run_with_items(second)
        unit_of_work.commit()
    with sqlalchemy_uow_factory() as reader:
        sql_read = reader.daily_feature_pipeline_runs.get_run_with_items(
            dotnet_written.run.daily_feature_pipeline_run_id
        )
    assert sql_read == dotnet_written

    pending = aggregate(universe_two, stored_feature_two.feature_snapshot_id, 713)
    with sqlalchemy_uow_factory() as unit_of_work:
        unit_of_work.daily_feature_pipeline_runs.add_run_with_items(pending)
    with dotnet_uow_factory() as reader:
        assert (
            reader.daily_feature_pipeline_runs.get_by_id(pending.run.daily_feature_pipeline_run_id)
            is None
        )
    with pytest.raises(DuplicateRecordError), dotnet_uow_factory() as unit_of_work:
        unit_of_work.daily_feature_pipeline_runs.add_run_with_items(first)
