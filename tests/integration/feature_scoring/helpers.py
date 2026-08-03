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
    factory: UnitOfWorkFactory,
    universe: UniverseSnapshot,
    *,
    horizon: int = 1,
    session: SessionDate = SESSION,
    now: datetime = NOW,
    case: int = 0,
    outcome_observation_shape: bool = False,
) -> DailyFeaturePipelineRunID:
    identifier_offset = case * 100
    run_id = DailyFeaturePipelineRunID(UUID(int=910_000 + identifier_offset))
    if outcome_observation_shape:
        snapshot_specs = (
            (1, "AAPL", Decimal("1"), FeatureQualityStatus.READY),
            (2, "MSFT", Decimal("3"), FeatureQualityStatus.DEGRADED),
        )
        unscorable_specs = ((3, "NVDA", DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT),)
        run_counts = (3, 1, 1, 1, 0, 0, 0, 0)
    else:
        snapshot_specs = (
            (1, "AAPL", Decimal("1"), FeatureQualityStatus.READY),
            (2, "MSFT", Decimal("3"), FeatureQualityStatus.READY),
            (3, "NVDA", Decimal("5"), FeatureQualityStatus.DEGRADED),
        )
        unscorable_specs = (
            (4, "AMZN", DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT),
            (5, "META", DailyFeaturePipelineItemOutcome.PROVIDER_ERROR),
        )
        run_counts = (5, 2, 1, 1, 0, 1, 0, 0)
    snapshots = tuple(
        _snapshot(
            *spec,
            horizon=horizon,
            identifier_offset=identifier_offset,
            source_case=case,
            now=now,
        )
        for spec in snapshot_specs
    )
    items = tuple(
        _scored_item(
            run_id,
            ordinal,
            symbol,
            snapshots[ordinal - 1],
            quality,
            session,
            identifier_offset,
            now,
        )
        for ordinal, symbol, _value, quality in snapshot_specs
    ) + tuple(
        _unscorable_item(
            run_id,
            ordinal,
            symbol,
            outcome,
            session,
            identifier_offset,
            now,
        )
        for ordinal, symbol, outcome in unscorable_specs
    )
    identity = DailyFeaturePipelineIdentity(
        universe.universe_snapshot_id,
        "TWELVE_DATA_TIME_SERIES",
        ExchangeCalendarCode.US_EQUITY_CORE,
        ExchangeCalendarVersion.V2026_1,
        session,
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        TradingDayHorizon(horizon),
        30,
        now,
        CompletionGracePeriod(timedelta(minutes=15)),
    )
    provisional = _run(run_id, identity, "0" * 64, run_counts, now)
    digest = daily_feature_pipeline_content_digest(
        provisional.stored(now),
        tuple(item.stored(now) for item in items),
    )
    aggregate = NewDailyFeaturePipelineRunWithItems(
        _run(run_id, identity, digest, run_counts, now), items
    )
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
    *,
    horizon: int,
    identifier_offset: int,
    source_case: int,
    now: datetime,
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
        TradingDayHorizon(horizon),
        now,
        values,
        (
            FeatureProvenanceEntry(
                "TWELVE_DATA_TIME_SERIES",
                f"p4a-scripted-{source_case}-{symbol}",
                now,
                now,
                f"{ordinal:064x}",
                "v1",
            ),
        ),
        quality,
        () if quality is FeatureQualityStatus.READY else ("VOLUME_DATA_INCOMPLETE",),
    )
    return NewFeatureSnapshot(
        FeatureSnapshotID(UUID(int=911_000 + identifier_offset + ordinal)),
        feature_snapshot_key(source),
        feature_content_digest(source),
        source,
        now,
    )


def _scored_item(
    run_id: DailyFeaturePipelineRunID,
    ordinal: int,
    symbol: str,
    snapshot: NewFeatureSnapshot,
    quality: FeatureQualityStatus,
    session: SessionDate,
    identifier_offset: int,
    now: datetime,
) -> NewDailyFeaturePipelineItem:
    return NewDailyFeaturePipelineItem(
        DailyFeaturePipelineItemID(UUID(int=912_000 + identifier_offset + ordinal)),
        run_id,
        ordinal,
        Symbol(symbol),
        "XNGS",
        session,
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
        now,
        now,
    )


def _unscorable_item(
    run_id: DailyFeaturePipelineRunID,
    ordinal: int,
    symbol: str,
    outcome: DailyFeaturePipelineItemOutcome,
    session: SessionDate,
    identifier_offset: int,
    now: datetime,
) -> NewDailyFeaturePipelineItem:
    return NewDailyFeaturePipelineItem(
        DailyFeaturePipelineItemID(UUID(int=912_000 + identifier_offset + ordinal)),
        run_id,
        ordinal,
        Symbol(symbol),
        "XNGS",
        session,
        outcome,
        0,
        0,
        None,
        None,
        outcome.value,
        0,
        0,
        now,
        now,
    )


def _run(
    run_id: DailyFeaturePipelineRunID,
    identity: DailyFeaturePipelineIdentity,
    digest: str,
    counts: tuple[int, ...],
    now: datetime,
) -> NewDailyFeaturePipelineRun:
    return NewDailyFeaturePipelineRun(
        run_id,
        daily_feature_run_key(identity),
        digest,
        identity,
        DailyFeaturePipelineRunStatus.COMPLETED_WITH_PARTIAL_FAILURES,
        *counts,
        0,
        0,
        now,
        now,
    )
