"""Orchestrate PIT bar selection and canonical FeatureSnapshot creation."""

from dataclasses import dataclass, field

from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    FeatureSnapshotCreationOutcome,
)
from auto_trading_v2.application.feature_building import (
    INSUFFICIENT_REASON,
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalFeatureBuilder,
    DailyTechnicalFeatureSnapshotBuildOutcome,
    DailyTechnicalFeatureSnapshotBuildResult,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.feature_snapshot import (
    FeatureSnapshotCreationService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis


@dataclass(frozen=True, slots=True)
class DailyTechnicalFeatureSnapshotService:
    unit_of_work_factory: UnitOfWorkFactory
    feature_snapshot_creation_service: FeatureSnapshotCreationService
    builder: DailyTechnicalFeatureBuilder = field(default_factory=DailyTechnicalFeatureBuilder)

    def build(
        self,
        command: BuildDailyTechnicalFeatureSnapshotCommand,
    ) -> DailyTechnicalFeatureSnapshotBuildResult:
        if not isinstance(command, BuildDailyTechnicalFeatureSnapshotCommand):
            raise TypeError("daily technical feature build command가 필요합니다.")
        with self.unit_of_work_factory() as unit_of_work:
            bars = unit_of_work.daily_market_bars.list_latest_available(
                command.source_code,
                command.symbol,
                DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
                command.as_of,
                21,
            )
        calculated = self.builder.build(
            symbol=command.symbol,
            source_code=command.source_code,
            as_of=command.as_of,
            horizon=command.horizon,
            bars=bars,
        )
        if calculated.outcome is DailyTechnicalCalculationOutcome.DATA_INSUFFICIENT:
            return DailyTechnicalFeatureSnapshotBuildResult(
                DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT,
                None,
                calculated.reason_codes or (INSUFFICIENT_REASON,),
            )
        source = calculated.snapshot_input
        if source is None:
            raise RuntimeError("daily technical calculation result is inconsistent")
        created = self.feature_snapshot_creation_service.create(
            CreateFeatureSnapshotCommand(
                symbol=source.symbol,
                feature_set_code=source.feature_set_code,
                feature_set_version=source.feature_set_version,
                horizon=source.horizon,
                as_of=source.as_of,
                feature_values=source.feature_values,
                provenance=source.provenance,
                quality_status=source.quality_status,
                quality_reason_codes=source.quality_reason_codes,
            )
        )
        outcome = (
            DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
            if created.outcome is FeatureSnapshotCreationOutcome.CREATED
            else DailyTechnicalFeatureSnapshotBuildOutcome.ALREADY_EXISTS
        )
        return DailyTechnicalFeatureSnapshotBuildResult(outcome, created.snapshot)
