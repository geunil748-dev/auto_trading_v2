from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshot,
    FeatureSnapshotInput,
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID, Symbol

NOW = datetime(2026, 7, 31, 21, tzinfo=UTC)
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


def feature_values(
    value: Decimal = Decimal("1"),
    *,
    volume: Decimal | None = Decimal("1"),
) -> dict[str, object]:
    rendered = format(value, "f")
    rendered_volume = None if volume is None else format(volume, "f")
    result: dict[str, object] = {key: rendered for key in PRICE_KEYS}
    result.update({key: rendered_volume for key in VOLUME_KEYS})
    result.update(
        last_close="100",
        completed_bar_count=21,
        adjustment_basis="SPLIT_ADJUSTED",
    )
    return result


def snapshot(
    *,
    identifier: int = 1,
    symbol: str = "AAPL",
    value: Decimal = Decimal("1"),
    quality: FeatureQualityStatus = FeatureQualityStatus.READY,
    reason: str | None = None,
) -> FeatureSnapshot:
    source = FeatureSnapshotInput(
        Symbol(symbol),
        "US_EQUITY_DAILY_TECHNICAL",
        "v1",
        TradingDayHorizon(1),
        NOW,
        feature_values(
            value,
            volume=value if quality is FeatureQualityStatus.READY else None,
        ),
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
        () if quality is FeatureQualityStatus.READY else (reason or "VOLUME_DATA_INCOMPLETE",),
    )
    return FeatureSnapshot(
        FeatureSnapshotID(UUID(int=identifier)),
        feature_snapshot_key(source),
        feature_content_digest(source),
        source,
        NOW,
        NOW,
    )


def snapshot_like(
    values: dict[str, object],
    *,
    quality: FeatureQualityStatus = FeatureQualityStatus.READY,
    reasons: tuple[str, ...] = (),
    feature_set_code: str = "US_EQUITY_DAILY_TECHNICAL",
    feature_set_version: str = "v1",
) -> object:
    return SimpleNamespace(
        snapshot_input=SimpleNamespace(
            feature_values=values,
            quality_status=quality,
            quality_reason_codes=reasons,
            feature_set_code=feature_set_code,
            feature_set_version=feature_set_version,
        )
    )
