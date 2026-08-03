from dataclasses import replace

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data.twelve_data import TWELVE_DATA_SOURCE_CODE
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyFeatureCommand,
    TwelveDataIngestionOutcome,
    TwelveDataIngestionResult,
    TwelveDataIngestionSummary,
)
from auto_trading_v2.application.feature_building import (
    BuildDailyPriceTechnicalFeatureSnapshotCommand,
    DailyTechnicalFeatureSnapshotBuildOutcome,
    DailyTechnicalFeatureSnapshotBuildResult,
)
from auto_trading_v2.application.services.twelve_data_daily_features import (
    TwelveDataDailyFeatureService,
)
from auto_trading_v2.application.services.twelve_data_daily_price_features import (
    TwelveDataDailyPriceFeatureService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from tests.unit.application.twelve_data.test_ingestion import NOW, command


class FakeIngestionService:
    def __init__(self, result: TwelveDataIngestionResult) -> None:
        self.result = result
        self.calls = []

    def ingest(self, ingestion_command):
        self.calls.append(ingestion_command)
        return self.result


class FakeFeatureService:
    def __init__(self) -> None:
        self.calls = []
        self.result = DailyTechnicalFeatureSnapshotBuildResult(
            DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT,
            None,
            ("INSUFFICIENT_COMPLETED_DAILY_BARS",),
        )

    def build(self, build_command):
        self.calls.append(build_command)
        return self.result


def ingestion_result(adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED):
    ingestion_command = command()
    summary = TwelveDataIngestionSummary(
        provider_code=TWELVE_DATA_SOURCE_CODE,
        symbol=ingestion_command.symbol,
        mic_code=ingestion_command.mic_code,
        adjustment_basis=adjustment_basis,
        completed_through_session_date=ingestion_command.completed_through_session_date,
        fetched_count=0,
        created_count=0,
        existing_count=0,
        oldest_session_date=None,
        newest_session_date=None,
    )
    return TwelveDataIngestionResult(TwelveDataIngestionOutcome.COMPLETED, summary)


def test_split_adjusted_ingestion_builds_only_the_same_provider_source() -> None:
    ingestion = FakeIngestionService(ingestion_result())
    feature = FakeFeatureService()
    subject = TwelveDataDailyFeatureService(
        ingestion,  # type: ignore[arg-type]
        feature,  # type: ignore[arg-type]
        FixedClock(NOW),
    )

    result = subject.ingest_and_build(
        TwelveDataDailyFeatureCommand(command(), TradingDayHorizon(3))
    )

    assert result.feature_snapshot is feature.result
    assert len(feature.calls) == 1
    assert feature.calls[0].source_code == TWELVE_DATA_SOURCE_CODE


def test_raw_ingestion_never_calls_technical_builder() -> None:
    raw_command = replace(command(), adjustment_basis=DailyMarketBarAdjustmentBasis.RAW)
    ingestion = FakeIngestionService(ingestion_result(DailyMarketBarAdjustmentBasis.RAW))
    feature = FakeFeatureService()
    subject = TwelveDataDailyFeatureService(
        ingestion,  # type: ignore[arg-type]
        feature,  # type: ignore[arg-type]
        FixedClock(NOW),
    )

    result = subject.ingest_and_build(
        TwelveDataDailyFeatureCommand(raw_command, TradingDayHorizon(3))
    )

    assert result.feature_snapshot is None
    assert feature.calls == []


def test_price_only_service_uses_explicit_v2_command_without_fallback() -> None:
    ingestion = FakeIngestionService(ingestion_result())
    feature = FakeFeatureService()
    subject = TwelveDataDailyPriceFeatureService(
        ingestion,  # type: ignore[arg-type]
        feature,  # type: ignore[arg-type]
        FixedClock(NOW),
    )

    result = subject.ingest_and_build(
        TwelveDataDailyFeatureCommand(command(), TradingDayHorizon(3))
    )

    assert result.feature_snapshot is feature.result
    assert len(ingestion.calls) == len(feature.calls) == 1
    assert isinstance(feature.calls[0], BuildDailyPriceTechnicalFeatureSnapshotCommand)
    assert feature.calls[0].source_code == TWELVE_DATA_SOURCE_CODE
