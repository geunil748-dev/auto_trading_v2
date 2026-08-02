from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidUniverseSnapshotIDFactory
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineItem,
    NewDailyFeaturePipelineRun,
    NewDailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.application.contracts.universes import CreateUniverseSnapshotCommand
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import UniverseSnapshotCreationService
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
    daily_feature_pipeline_content_digest,
    daily_feature_run_key,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.market_calendar import (
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    FeatureSnapshotID,
    IdentifierFactory,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.universes import UniverseMember, UniverseSnapshot

NOW = datetime(2026, 7, 31, 0, tzinfo=UTC)


def universe_command(case: int, *symbols: str) -> CreateUniverseSnapshotCommand:
    return CreateUniverseSnapshotCommand(
        f"P3_INTEGRATION_{case}",
        "v1",
        tuple(UniverseMember(Symbol(symbol), "XNGS") for symbol in symbols),
    )


def universe_service(
    factory: UnitOfWorkFactory,
    identifier: int,
    observed_at: datetime | None = None,
) -> UniverseSnapshotCreationService:
    ids = IdentifierFactory(lambda: UUID(int=identifier))
    return UniverseSnapshotCreationService(
        factory,
        FixedClock(NOW - timedelta(days=1) if observed_at is None else observed_at),
        UuidUniverseSnapshotIDFactory(ids),
    )


def aggregate(
    universe: UniverseSnapshot,
    feature_snapshot_id: FeatureSnapshotID,
    case: int,
) -> NewDailyFeaturePipelineRunWithItems:
    run_id = DailyFeaturePipelineRunID(UUID(int=case * 100))
    completed = SessionDate(date(2026, 7, 30))
    identity = DailyFeaturePipelineIdentity(
        universe.universe_snapshot_id,
        "TWELVE_DATA_TIME_SERIES",
        ExchangeCalendarCode.US_EQUITY_CORE,
        ExchangeCalendarVersion.V2026_1,
        completed,
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        TradingDayHorizon(1),
        30,
        NOW + timedelta(minutes=case),
        CompletionGracePeriod(timedelta(minutes=15)),
    )
    key = daily_feature_run_key(identity)
    items = (
        NewDailyFeaturePipelineItem(
            DailyFeaturePipelineItemID(UUID(int=case * 100 + 1)),
            run_id,
            1,
            Symbol("AAPL"),
            "XNGS",
            completed,
            DailyFeaturePipelineItemOutcome.READY,
            21,
            0,
            feature_snapshot_id,
            FeatureQualityStatus.READY,
            None,
            1,
            1,
            NOW,
            NOW,
        ),
        NewDailyFeaturePipelineItem(
            DailyFeaturePipelineItemID(UUID(int=case * 100 + 2)),
            run_id,
            2,
            Symbol("MSFT"),
            "XNGS",
            completed,
            DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT,
            10,
            0,
            None,
            None,
            "INSUFFICIENT_COMPLETED_DAILY_BARS",
            1,
            1,
            NOW,
            NOW,
        ),
    )
    provisional = _run(run_id, key, "0" * 64, identity)
    digest = daily_feature_pipeline_content_digest(
        provisional.stored(NOW),
        tuple(item.stored(NOW) for item in items),
    )
    return NewDailyFeaturePipelineRunWithItems(
        _run(run_id, key, digest, identity),
        items,
    )


def _run(
    run_id: DailyFeaturePipelineRunID,
    key: str,
    digest: str,
    identity: DailyFeaturePipelineIdentity,
) -> NewDailyFeaturePipelineRun:
    return NewDailyFeaturePipelineRun(
        run_id,
        key,
        digest,
        identity,
        DailyFeaturePipelineRunStatus.COMPLETED_WITH_WARNINGS,
        2,
        1,
        0,
        1,
        0,
        0,
        0,
        0,
        2,
        2,
        NOW,
        NOW,
    )
