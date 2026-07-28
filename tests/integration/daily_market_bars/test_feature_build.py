from datetime import timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.feature_building import (
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from tests.integration.daily_market_bars.helpers import (
    build_command,
    command,
    feature_service,
    new_bar,
    persist_series,
    revised,
)

pytestmark = pytest.mark.integration


def test_sqlalchemy_bars_build_ready_snapshot_retry_and_provenance(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    bars = persist_series(sqlalchemy_uow_factory, 241)
    as_of = command(241, 20).available_at
    future = revised(
        command(241, 20),
        revision="future",
        available_at=as_of + timedelta(minutes=1),
        close_delta=Decimal(5),
    )
    with sqlalchemy_uow_factory() as unit_of_work:
        unit_of_work.daily_market_bars.add(new_bar(future, 241998))
        unit_of_work.commit()
    service = feature_service(sqlalchemy_uow_factory, as_of, 241999)
    source = build_command(241, as_of)

    created = service.build(source)
    retried = service.build(source)

    assert created.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
    assert retried.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.ALREADY_EXISTS
    assert created.snapshot == retried.snapshot
    snapshot = created.snapshot
    assert snapshot is not None
    assert snapshot.snapshot_input.quality_status is FeatureQualityStatus.READY
    assert len(snapshot.snapshot_input.provenance) == 21
    assert {entry.content_digest for entry in snapshot.snapshot_input.provenance} == {
        bar.content_digest for bar in bars
    }


def test_dotnet_bars_build_ready_snapshot_through_dotnet_uow(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    bars = persist_series(dotnet_uow_factory, 242)
    as_of = command(242, 20).available_at

    result = feature_service(dotnet_uow_factory, as_of, 242999).build(build_command(242, as_of))

    assert result.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
    assert result.snapshot is not None
    assert {entry.content_digest for entry in result.snapshot.snapshot_input.provenance} == {
        bar.content_digest for bar in bars
    }


def test_degraded_and_data_insufficient_are_distinct_normal_outcomes(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    persist_series(sqlalchemy_uow_factory, 243, volume_none_at=7)
    degraded_as_of = command(243, 20).available_at
    degraded = feature_service(
        sqlalchemy_uow_factory,
        degraded_as_of,
        243999,
    ).build(build_command(243, degraded_as_of))

    assert degraded.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
    assert degraded.snapshot is not None
    assert degraded.snapshot.snapshot_input.quality_status is FeatureQualityStatus.DEGRADED
    assert degraded.snapshot.snapshot_input.quality_reason_codes == ("VOLUME_DATA_INCOMPLETE",)

    persist_series(sqlalchemy_uow_factory, 244, count=20)
    insufficient_as_of = command(244, 20).available_at
    insufficient = feature_service(
        sqlalchemy_uow_factory,
        insufficient_as_of,
        244999,
    ).build(build_command(244, insufficient_as_of))
    assert insufficient.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT
    assert insufficient.snapshot is None
