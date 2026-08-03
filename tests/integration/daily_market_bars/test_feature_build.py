from datetime import timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.feature_building import (
    PRICE_FEATURE_NAMES,
    PRICE_ONLY_FEATURE_SET_VERSION,
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from tests.integration.daily_market_bars.helpers import (
    build_command,
    command,
    feature_service,
    new_bar,
    persist_series,
    price_build_command,
    price_feature_service,
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


@pytest.mark.parametrize("case,volume_none_at", [(245, 7), (246, None)])
def test_v1_v2_price_parity_and_dotnet_v2_read(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
    case: int,
    volume_none_at: int | None,
) -> None:
    persist_series(sqlalchemy_uow_factory, case, volume_none_at=volume_none_at)
    as_of = command(case, 20).available_at
    v1 = feature_service(sqlalchemy_uow_factory, as_of, case * 1000 + 997).build(
        build_command(case, as_of)
    )
    v2 = price_feature_service(sqlalchemy_uow_factory, as_of, case * 1000 + 998).build(
        price_build_command(case, as_of)
    )

    assert v1.snapshot is not None and v2.snapshot is not None
    v1_input = v1.snapshot.snapshot_input
    v2_input = v2.snapshot.snapshot_input
    assert all(
        v1_input.feature_values[name] == v2_input.feature_values[name]
        for name in PRICE_FEATURE_NAMES
    )
    assert v2_input.feature_set_version == PRICE_ONLY_FEATURE_SET_VERSION
    assert v2_input.quality_status is FeatureQualityStatus.READY
    assert not {
        "volume_ratio_5_to_20",
        "latest_volume_to_avg20",
        "average_dollar_volume_20",
    }.intersection(v2_input.feature_values)
    expected_v1 = (
        FeatureQualityStatus.DEGRADED if volume_none_at is not None else FeatureQualityStatus.READY
    )
    assert v1_input.quality_status is expected_v1
    with dotnet_uow_factory() as reader:
        dotnet_v2 = reader.feature_snapshots.get_by_id(v2.snapshot.feature_snapshot_id)
    assert dotnet_v2 == v2.snapshot
