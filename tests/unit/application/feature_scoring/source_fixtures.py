from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineItem,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunStatus,
    DailyFeaturePipelineRunWithItems,
    daily_feature_pipeline_content_digest,
    daily_feature_run_key,
)
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshot,
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
    UniverseSnapshotID,
)

NOW = datetime(2026, 7, 31, 21, tzinfo=UTC)
SESSION = SessionDate(date(2026, 7, 31))


def snapshot(
    *,
    identifier: int,
    symbol: str,
    value: Decimal = Decimal("1"),
    quality: FeatureQualityStatus = FeatureQualityStatus.READY,
) -> FeatureSnapshot:
    price_keys = (
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
    values: dict[str, object] = {key: value for key in price_keys}
    volume = value if quality is FeatureQualityStatus.READY else None
    values.update(
        volume_ratio_5_to_20=volume,
        latest_volume_to_avg20=volume,
        average_dollar_volume_20=volume,
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
                f"bar-{identifier}",
                NOW,
                NOW,
                f"{identifier:064x}",
                "v1",
            ),
        ),
        quality,
        () if quality is FeatureQualityStatus.READY else ("VOLUME_DATA_INCOMPLETE",),
    )
    return FeatureSnapshot(
        FeatureSnapshotID(UUID(int=identifier)),
        feature_snapshot_key(source),
        feature_content_digest(source),
        source,
        NOW,
        NOW,
    )


def pipeline_aggregate(
    specs: tuple[tuple[str, DailyFeaturePipelineItemOutcome], ...],
    *,
    status: DailyFeaturePipelineRunStatus = DailyFeaturePipelineRunStatus.COMPLETED,
) -> tuple[DailyFeaturePipelineRunWithItems, dict[UUID, FeatureSnapshot]]:
    run_id = DailyFeaturePipelineRunID(UUID(int=100))
    identity = DailyFeaturePipelineIdentity(
        UniverseSnapshotID(UUID(int=99)),
        "TWELVE_DATA_TIME_SERIES",
        ExchangeCalendarCode("US_EQUITY_CORE"),
        ExchangeCalendarVersion("2026.v1"),
        SESSION,
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        TradingDayHorizon(1),
        30,
        NOW,
        CompletionGracePeriod(timedelta(minutes=15)),
    )
    snapshots: dict[UUID, FeatureSnapshot] = {}
    items: list[DailyFeaturePipelineItem] = []
    for ordinal, (symbol, outcome) in enumerate(specs, start=1):
        quality = {
            DailyFeaturePipelineItemOutcome.READY: FeatureQualityStatus.READY,
            DailyFeaturePipelineItemOutcome.DEGRADED: FeatureQualityStatus.DEGRADED,
        }.get(outcome)
        feature = None
        if quality is not None:
            feature = snapshot(
                identifier=1000 + ordinal,
                symbol=symbol,
                value=Decimal(ordinal),
                quality=quality,
            )
            snapshots[feature.feature_snapshot_id.value] = feature
        items.append(
            DailyFeaturePipelineItem(
                DailyFeaturePipelineItemID(UUID(int=200 + ordinal)),
                run_id,
                ordinal,
                Symbol(symbol),
                "XNGS",
                SESSION,
                outcome,
                0,
                21 if feature is not None else 0,
                None if feature is None else feature.feature_snapshot_id,
                quality,
                None if feature is not None else outcome.value,
                0,
                0,
                NOW,
                NOW,
                NOW,
            )
        )
    counts = _pipeline_counts(items)
    provisional = DailyFeaturePipelineRun(
        run_id,
        daily_feature_run_key(identity),
        "0" * 64,
        identity,
        status,
        len(items),
        **counts,
        estimated_credit_count=0,
        consumed_credit_count=0,
        started_at=NOW,
        finished_at=NOW,
        recorded_at=NOW,
    )
    digest = daily_feature_pipeline_content_digest(provisional, tuple(items))
    run = DailyFeaturePipelineRun(
        run_id,
        provisional.run_key,
        digest,
        identity,
        status,
        len(items),
        **counts,
        estimated_credit_count=0,
        consumed_credit_count=0,
        started_at=NOW,
        finished_at=NOW,
        recorded_at=NOW,
    )
    return DailyFeaturePipelineRunWithItems(run, tuple(items)), snapshots


def _pipeline_counts(items: list[DailyFeaturePipelineItem]) -> dict[str, int]:
    outcomes = DailyFeaturePipelineItemOutcome
    return {
        "ready_count": sum(item.outcome is outcomes.READY for item in items),
        "degraded_count": sum(item.outcome is outcomes.DEGRADED for item in items),
        "data_insufficient_count": sum(
            item.outcome is outcomes.DATA_INSUFFICIENT for item in items
        ),
        "no_data_count": sum(item.outcome is outcomes.NO_DATA for item in items),
        "provider_error_count": sum(item.outcome is outcomes.PROVIDER_ERROR for item in items),
        "calendar_error_count": sum(item.outcome is outcomes.CALENDAR_ERROR for item in items),
        "not_attempted_count": sum(
            item.outcome in {outcomes.NOT_ATTEMPTED_ABORTED, outcomes.NOT_ATTEMPTED_BUDGET}
            for item in items
        ),
    }
