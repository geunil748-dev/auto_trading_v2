from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineItem,
    NewDailyFeaturePipelineRun,
    NewDailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.application.contracts.feature_snapshots import NewFeatureSnapshot
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
    daily_feature_pipeline_content_digest,
    daily_feature_run_key,
)
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshotInput,
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.market_calendar import (
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.universes import UniverseSnapshot

NOW = datetime(2026, 7, 31, 0, tzinfo=UTC)
SESSION = SessionDate(date(2026, 7, 30))
PRICE_KEYS = (
    "one_day_return",
    "five_day_return",
    "twenty_day_return",
    "close_vs_sma5",
    "close_vs_sma10",
    "close_vs_sma20",
    "distance_from_prior_20d_high",
    "distance_from_prior_20d_low",
    "latest_gap_return",
    "latest_intraday_return",
    "latest_range_rate",
    "realized_volatility_20d",
    "atr14_rate",
)
VOLUME_KEYS = (
    "volume_ratio_5_to_20",
    "latest_volume_to_avg20",
    "average_dollar_volume_20",
)


def seed_source(
    factory: UnitOfWorkFactory, universe: UniverseSnapshot
) -> DailyFeaturePipelineRunID:
    run_id = DailyFeaturePipelineRunID(UUID(int=910_000))
    snapshot_specs = (
        (1, "AAPL", Decimal("1"), FeatureQualityStatus.READY),
        (2, "MSFT", Decimal("3"), FeatureQualityStatus.READY),
        (3, "NVDA", Decimal("5"), FeatureQualityStatus.DEGRADED),
    )
    snapshots = tuple(_snapshot(*spec) for spec in snapshot_specs)
    items = (
        _scored_item(run_id, 1, "AAPL", snapshots[0], FeatureQualityStatus.READY),
        _scored_item(run_id, 2, "MSFT", snapshots[1], FeatureQualityStatus.READY),
        _scored_item(run_id, 3, "NVDA", snapshots[2], FeatureQualityStatus.DEGRADED),
        _unscorable_item(
            run_id,
            4,
            "AMZN",
            DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT,
        ),
        _unscorable_item(run_id, 5, "META", DailyFeaturePipelineItemOutcome.PROVIDER_ERROR),
    )
    identity = DailyFeaturePipelineIdentity(
        universe.universe_snapshot_id,
        "TWELVE_DATA_TIME_SERIES",
        ExchangeCalendarCode.US_EQUITY_CORE,
        ExchangeCalendarVersion.V2026_1,
        SESSION,
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        TradingDayHorizon(1),
        30,
        NOW,
        CompletionGracePeriod(timedelta(minutes=15)),
    )
    provisional = _run(run_id, identity, "0" * 64)
    digest = daily_feature_pipeline_content_digest(
        provisional.stored(NOW),
        tuple(item.stored(NOW) for item in items),
    )
    aggregate = NewDailyFeaturePipelineRunWithItems(_run(run_id, identity, digest), items)
    with factory() as unit_of_work:
        for snapshot in snapshots:
            unit_of_work.feature_snapshots.add(snapshot)
        unit_of_work.daily_feature_pipeline_runs.add_run_with_items(aggregate)
        unit_of_work.commit()
    return run_id


def _snapshot(
    ordinal: int,
    symbol: str,
    value: Decimal,
    quality: FeatureQualityStatus,
) -> NewFeatureSnapshot:
    values: dict[str, object] = {key: value for key in PRICE_KEYS}
    values.update(
        {key: value if quality is FeatureQualityStatus.READY else None for key in VOLUME_KEYS}
    )
    values.update(
        last_close=Decimal("100"),
        completed_bar_count=21,
        adjustment_basis="SPLIT_ADJUSTED",
    )
    source = FeatureSnapshotInput(
        Symbol(symbol),
        "US_EQUITY_DAILY_TECHNICAL",
        "v1",
        TradingDayHorizon(1),
        NOW,
        values,
        (
            FeatureProvenanceEntry(
                "TWELVE_DATA_TIME_SERIES",
                f"p4a-scripted-{symbol}",
                NOW,
                NOW,
                f"{ordinal:064x}",
                "v1",
            ),
        ),
        quality,
        () if quality is FeatureQualityStatus.READY else ("VOLUME_DATA_INCOMPLETE",),
    )
    return NewFeatureSnapshot(
        FeatureSnapshotID(UUID(int=911_000 + ordinal)),
        feature_snapshot_key(source),
        feature_content_digest(source),
        source,
        NOW,
    )


def _scored_item(
    run_id: DailyFeaturePipelineRunID,
    ordinal: int,
    symbol: str,
    snapshot: NewFeatureSnapshot,
    quality: FeatureQualityStatus,
) -> NewDailyFeaturePipelineItem:
    return NewDailyFeaturePipelineItem(
        DailyFeaturePipelineItemID(UUID(int=912_000 + ordinal)),
        run_id,
        ordinal,
        Symbol(symbol),
        "XNGS",
        SESSION,
        (
            DailyFeaturePipelineItemOutcome.READY
            if quality is FeatureQualityStatus.READY
            else DailyFeaturePipelineItemOutcome.DEGRADED
        ),
        0,
        21,
        snapshot.feature_snapshot_id,
        quality,
        None if quality is FeatureQualityStatus.READY else "VOLUME_DATA_INCOMPLETE",
        0,
        0,
        NOW,
        NOW,
    )


def _unscorable_item(
    run_id: DailyFeaturePipelineRunID,
    ordinal: int,
    symbol: str,
    outcome: DailyFeaturePipelineItemOutcome,
) -> NewDailyFeaturePipelineItem:
    return NewDailyFeaturePipelineItem(
        DailyFeaturePipelineItemID(UUID(int=912_000 + ordinal)),
        run_id,
        ordinal,
        Symbol(symbol),
        "XNGS",
        SESSION,
        outcome,
        0,
        0,
        None,
        None,
        outcome.value,
        0,
        0,
        NOW,
        NOW,
    )


def _run(
    run_id: DailyFeaturePipelineRunID,
    identity: DailyFeaturePipelineIdentity,
    digest: str,
) -> NewDailyFeaturePipelineRun:
    return NewDailyFeaturePipelineRun(
        run_id,
        daily_feature_run_key(identity),
        digest,
        identity,
        DailyFeaturePipelineRunStatus.COMPLETED_WITH_PARTIAL_FAILURES,
        5,
        2,
        1,
        1,
        0,
        1,
        0,
        0,
        0,
        0,
        NOW,
        NOW,
    )
