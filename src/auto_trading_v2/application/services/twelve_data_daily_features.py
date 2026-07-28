"""Explicit Twelve Data ingestion-to-feature orchestration without fallback."""

from dataclasses import dataclass

from auto_trading_v2.adapters.market_data.twelve_data import TWELVE_DATA_SOURCE_CODE
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyFeatureCommand,
    TwelveDataDailyFeatureResult,
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.feature_building import (
    BuildDailyTechnicalFeatureSnapshotCommand,
)
from auto_trading_v2.application.services.daily_technical_feature_snapshot import (
    DailyTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.ports.clock import Clock

_BUILDABLE = frozenset(
    {
        TwelveDataIngestionOutcome.COMPLETED,
        TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING,
    }
)


@dataclass(frozen=True, slots=True)
class TwelveDataDailyFeatureService:
    ingestion_service: TwelveDataDailyMarketBarIngestionService
    feature_service: DailyTechnicalFeatureSnapshotService
    clock: Clock

    def ingest_and_build(
        self,
        command: TwelveDataDailyFeatureCommand,
    ) -> TwelveDataDailyFeatureResult:
        ingested = self.ingestion_service.ingest(command.ingestion)
        if (
            ingested.outcome not in _BUILDABLE
            or command.ingestion.adjustment_basis
            is not DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
        ):
            return TwelveDataDailyFeatureResult(ingested, None)
        built = self.feature_service.build(
            BuildDailyTechnicalFeatureSnapshotCommand(
                source_code=TWELVE_DATA_SOURCE_CODE,
                symbol=command.ingestion.symbol,
                as_of=self.clock.now_utc(),
                horizon=command.horizon,
            )
        )
        return TwelveDataDailyFeatureResult(ingested, built)
