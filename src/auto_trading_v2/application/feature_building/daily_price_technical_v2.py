"""Pure price-only US equity daily technical FeatureSet v2."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from auto_trading_v2.application.feature_building.contracts import (
    PRICE_ONLY_FEATURE_SET_CODE,
    PRICE_ONLY_FEATURE_SET_VERSION,
    BuildDailyPriceTechnicalFeatureSnapshotCommand,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalCalculationResult,
)
from auto_trading_v2.application.feature_building.daily_technical import (
    DailyTechnicalFeatureBuilder,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBar
from auto_trading_v2.domain.feature_snapshots import (
    FeatureQualityStatus,
    FeatureSnapshotInput,
    TradingDayHorizon,
)
from auto_trading_v2.domain.primitives import Symbol

PRICE_FEATURE_NAMES = (
    "last_close",
    "one_day_return",
    "five_day_return",
    "twenty_day_return",
    "latest_gap_return",
    "latest_intraday_return",
    "latest_range_rate",
    "close_vs_sma5",
    "close_vs_sma10",
    "close_vs_sma20",
    "realized_volatility_20d",
    "atr14_rate",
    "distance_from_prior_20d_high",
    "distance_from_prior_20d_low",
)
PRICE_ONLY_METADATA_NAMES = ("adjustment_basis", "completed_bar_count")


@dataclass(frozen=True, slots=True)
class DailyPriceTechnicalFeatureBuilderV2:
    """Reuse the frozen v1 Decimal calculations and omit every volume key."""

    v1_builder: DailyTechnicalFeatureBuilder = field(default_factory=DailyTechnicalFeatureBuilder)

    def build(
        self,
        *,
        symbol: Symbol,
        source_code: str,
        as_of: datetime,
        horizon: TradingDayHorizon,
        bars: Sequence[DailyMarketBar],
    ) -> DailyTechnicalCalculationResult:
        request = BuildDailyPriceTechnicalFeatureSnapshotCommand(
            source_code,
            symbol,
            as_of,
            horizon,
        )
        calculated = self.v1_builder.build(
            symbol=request.symbol,
            source_code=request.source_code,
            as_of=request.as_of,
            horizon=request.horizon,
            bars=bars,
        )
        if calculated.outcome is DailyTechnicalCalculationOutcome.DATA_INSUFFICIENT:
            return calculated
        source = calculated.snapshot_input
        if source is None:
            raise RuntimeError("daily price technical calculation result is inconsistent")
        names = (*PRICE_FEATURE_NAMES, *PRICE_ONLY_METADATA_NAMES)
        snapshot_input = FeatureSnapshotInput(
            symbol=source.symbol,
            feature_set_code=PRICE_ONLY_FEATURE_SET_CODE,
            feature_set_version=PRICE_ONLY_FEATURE_SET_VERSION,
            horizon=source.horizon,
            as_of=source.as_of,
            feature_values={name: source.feature_values[name] for name in names},
            provenance=source.provenance,
            quality_status=FeatureQualityStatus.READY,
            quality_reason_codes=(),
        )
        return DailyTechnicalCalculationResult(
            DailyTechnicalCalculationOutcome.SNAPSHOT_READY,
            snapshot_input,
        )
