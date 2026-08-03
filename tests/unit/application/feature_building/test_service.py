from __future__ import annotations

from types import TracebackType
from typing import cast
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    FeatureSnapshotCreationOutcome,
    FeatureSnapshotCreationResult,
    NewFeatureSnapshot,
)
from auto_trading_v2.application.feature_building import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    PRICE_ONLY_FEATURE_SET_VERSION,
    BuildDailyPriceTechnicalFeatureSnapshotCommand,
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_price_technical_feature_snapshot import (
    DailyPriceTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.daily_technical_feature_snapshot import (
    DailyTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.feature_snapshot import (
    FeatureSnapshotCreationService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_snapshots import (
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID, Symbol
from tests.unit.domain.daily_market_bars.helpers import BASE_TIME, stored_bar


class FakeBarRepository:
    def __init__(self, bars: tuple[object, ...]) -> None:
        self.bars = bars
        self.calls: list[tuple[object, ...]] = []

    def list_latest_available(self, *args: object) -> tuple[object, ...]:
        self.calls.append(args)
        return self.bars


class ReadUnitOfWork:
    def __init__(self, repository: FakeBarRepository) -> None:
        self.daily_market_bars = repository
        self.commit_calls = 0
        self.rollback_calls = 0
        self.exit_calls = 0

    def __enter__(self) -> ReadUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_calls += 1


class ReadFactory:
    def __init__(self, unit: ReadUnitOfWork) -> None:
        self.unit = unit
        self.calls = 0

    def __call__(self) -> ReadUnitOfWork:
        self.calls += 1
        return self.unit


class FakeSnapshotCreationService:
    def __init__(self, outcome: FeatureSnapshotCreationOutcome) -> None:
        self.outcome = outcome
        self.calls: list[CreateFeatureSnapshotCommand] = []

    def create(
        self,
        command: CreateFeatureSnapshotCommand,
    ) -> FeatureSnapshotCreationResult:
        self.calls.append(command)
        source = command.snapshot_input
        snapshot = NewFeatureSnapshot(
            FeatureSnapshotID(UUID(int=500)),
            feature_snapshot_key(source),
            feature_content_digest(source),
            source,
            source.as_of,
        ).stored(source.as_of)
        return FeatureSnapshotCreationResult(self.outcome, snapshot)


def _command() -> BuildDailyTechnicalFeatureSnapshotCommand:
    return BuildDailyTechnicalFeatureSnapshotCommand(
        source_code="UNIT_SOURCE",
        symbol=Symbol("AAPL"),
        as_of=BASE_TIME.replace(year=2027),
        horizon=TradingDayHorizon(3),
    )


def _service(
    bars: tuple[object, ...],
    outcome: FeatureSnapshotCreationOutcome = FeatureSnapshotCreationOutcome.CREATED,
) -> tuple[
    DailyTechnicalFeatureSnapshotService,
    FakeBarRepository,
    ReadUnitOfWork,
    FakeSnapshotCreationService,
]:
    repository = FakeBarRepository(bars)
    unit = ReadUnitOfWork(repository)
    creation = FakeSnapshotCreationService(outcome)
    service = DailyTechnicalFeatureSnapshotService(
        cast(UnitOfWorkFactory, ReadFactory(unit)),
        cast(FeatureSnapshotCreationService, creation),
    )
    return service, repository, unit, creation


def test_data_insufficient_has_no_snapshot_write_or_commit() -> None:
    service, repository, unit, creation = _service(tuple(stored_bar(index) for index in range(20)))

    result = service.build(_command())

    assert result.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT
    assert result.snapshot is None
    assert result.reason_codes == ("INSUFFICIENT_COMPLETED_DAILY_BARS",)
    assert creation.calls == []
    assert unit.commit_calls == unit.rollback_calls == 0
    assert unit.exit_calls == 1
    assert repository.calls[0][2] is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
    assert repository.calls[0][4] == 21


@pytest.mark.parametrize(
    ("creation_outcome", "build_outcome"),
    [
        (
            FeatureSnapshotCreationOutcome.CREATED,
            DailyTechnicalFeatureSnapshotBuildOutcome.CREATED,
        ),
        (
            FeatureSnapshotCreationOutcome.ALREADY_EXISTS,
            DailyTechnicalFeatureSnapshotBuildOutcome.ALREADY_EXISTS,
        ),
    ],
)
def test_ready_result_maps_creation_outcome_and_fixed_contract(
    creation_outcome: FeatureSnapshotCreationOutcome,
    build_outcome: DailyTechnicalFeatureSnapshotBuildOutcome,
) -> None:
    service, repository, unit, creation = _service(
        tuple(stored_bar(index) for index in range(21)),
        creation_outcome,
    )

    result = service.build(_command())

    assert result.outcome is build_outcome
    assert result.snapshot is not None
    assert len(creation.calls) == 1
    called = creation.calls[0]
    assert called.feature_set_code == FEATURE_SET_CODE
    assert called.feature_set_version == FEATURE_SET_VERSION
    assert called.feature_values["adjustment_basis"] == "SPLIT_ADJUSTED"
    assert called.provenance
    assert unit.commit_calls == 0
    assert repository.calls[0][0:2] == ("UNIT_SOURCE", Symbol("AAPL"))


def test_degraded_price_snapshot_is_still_created_with_safe_reason() -> None:
    bars = tuple(stored_bar(index, volume=None if index == 5 else 1000) for index in range(21))
    service, _, _, creation = _service(bars)

    result = service.build(_command())

    assert result.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
    assert creation.calls[0].quality_reason_codes == ("VOLUME_DATA_INCOMPLETE",)


def test_price_only_v2_insufficient_never_writes_and_null_volume_is_ready() -> None:
    repository = FakeBarRepository(tuple(stored_bar(index) for index in range(20)))
    unit = ReadUnitOfWork(repository)
    creation = FakeSnapshotCreationService(FeatureSnapshotCreationOutcome.CREATED)
    service = DailyPriceTechnicalFeatureSnapshotService(
        cast(UnitOfWorkFactory, ReadFactory(unit)),
        cast(FeatureSnapshotCreationService, creation),
    )
    command = BuildDailyPriceTechnicalFeatureSnapshotCommand(
        "UNIT_SOURCE", Symbol("AAPL"), BASE_TIME.replace(year=2027), TradingDayHorizon(3)
    )

    insufficient = service.build(command)
    repository.bars = tuple(stored_bar(index, volume=None) for index in range(21))
    ready = service.build(command)

    assert insufficient.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT
    assert insufficient.snapshot is None
    assert unit.commit_calls == 0
    assert len(creation.calls) == 1
    assert ready.snapshot is not None
    assert creation.calls[0].feature_set_version == PRICE_ONLY_FEATURE_SET_VERSION
    assert creation.calls[0].quality_status.name == "READY"
