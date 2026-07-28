"""Pure Decimal implementation of US equity daily technical feature set v1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from auto_trading_v2.application.feature_building.contracts import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    INSUFFICIENT_REASON,
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalCalculationResult,
)
from auto_trading_v2.application.feature_building.errors import (
    DailyTechnicalFeatureBuildError,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
)
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshotInput,
    TradingDayHorizon,
)
from auto_trading_v2.domain.primitives import Symbol

_REQUIRED_BAR_COUNT = 21
_DECIMAL_CONTEXT = Context(prec=38, rounding=ROUND_HALF_EVEN)
_ZERO = Decimal(0)
_TWENTY = Decimal(20)


@dataclass(frozen=True, slots=True)
class DailyTechnicalFeatureBuilder:
    """Build a deterministic snapshot input without I/O or generated values."""

    def build(
        self,
        *,
        symbol: Symbol,
        source_code: str,
        as_of: datetime,
        horizon: TradingDayHorizon,
        bars: Sequence[DailyMarketBar],
    ) -> DailyTechnicalCalculationResult:
        request = BuildDailyTechnicalFeatureSnapshotCommand(
            source_code=source_code,
            symbol=symbol,
            as_of=as_of,
            horizon=horizon,
        )
        ordered = self._validated_ordered_bars(
            symbol=request.symbol,
            source_code=request.source_code,
            as_of=request.as_of,
            bars=bars,
        )
        if len(ordered) < _REQUIRED_BAR_COUNT:
            return DailyTechnicalCalculationResult(
                DailyTechnicalCalculationOutcome.DATA_INSUFFICIENT,
                None,
                (INSUFFICIENT_REASON,),
            )
        selected = ordered[-_REQUIRED_BAR_COUNT:]
        values, quality, reasons = self._calculate(selected)
        provenance = tuple(
            FeatureProvenanceEntry(
                source_code=bar.bar_input.source_code,
                source_record_key=bar.bar_input.source_record_key,
                source_version=bar.bar_input.source_version,
                observed_at=bar.bar_input.observed_at,
                available_at=bar.bar_input.available_at,
                content_digest=bar.content_digest,
            )
            for bar in selected
        )
        snapshot_input = FeatureSnapshotInput(
            symbol=request.symbol,
            feature_set_code=FEATURE_SET_CODE,
            feature_set_version=FEATURE_SET_VERSION,
            horizon=request.horizon,
            as_of=request.as_of,
            feature_values=values,
            provenance=provenance,
            quality_status=quality,
            quality_reason_codes=reasons,
        )
        return DailyTechnicalCalculationResult(
            DailyTechnicalCalculationOutcome.SNAPSHOT_READY,
            snapshot_input,
        )

    @staticmethod
    def _validated_ordered_bars(
        *,
        symbol: Symbol,
        source_code: str,
        as_of: datetime,
        bars: Sequence[DailyMarketBar],
    ) -> tuple[DailyMarketBar, ...]:
        if isinstance(bars, str | bytes) or not isinstance(bars, Sequence):
            raise DailyTechnicalFeatureBuildError("bars는 DailyMarketBar 시퀀스여야 합니다.")
        if any(not isinstance(bar, DailyMarketBar) for bar in bars):
            raise DailyTechnicalFeatureBuildError("bars 원소 타입이 올바르지 않습니다.")
        if any(bar.bar_input.symbol != symbol for bar in bars):
            raise DailyTechnicalFeatureBuildError("서로 다른 symbol의 bar를 혼합할 수 없습니다.")
        if any(bar.bar_input.source_code != source_code for bar in bars):
            raise DailyTechnicalFeatureBuildError("서로 다른 source의 bar를 혼합할 수 없습니다.")
        if any(bar.bar_input.currency.code != "USD" for bar in bars):
            raise DailyTechnicalFeatureBuildError("USD 외 bar는 계산할 수 없습니다.")
        if any(
            bar.bar_input.adjustment_basis is not DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
            for bar in bars
        ):
            raise DailyTechnicalFeatureBuildError("SPLIT_ADJUSTED bar만 계산할 수 있습니다.")
        if any(bar.bar_input.available_at > as_of for bar in bars):
            raise DailyTechnicalFeatureBuildError("as_of 이후 bar는 계산에 사용할 수 없습니다.")
        ordered = tuple(sorted(bars, key=lambda bar: bar.bar_input.session_date.value))
        dates = tuple(bar.bar_input.session_date for bar in ordered)
        if len(dates) != len(set(dates)):
            raise DailyTechnicalFeatureBuildError("중복 session_date는 허용되지 않습니다.")
        return ordered

    @staticmethod
    def _calculate(
        bars: tuple[DailyMarketBar, ...],
    ) -> tuple[dict[str, object], FeatureQualityStatus, tuple[str, ...]]:
        inputs = tuple(bar.bar_input for bar in bars)
        close = tuple(bar.close_price for bar in inputs)
        with localcontext(_DECIMAL_CONTEXT):
            returns = tuple(close[index] / close[index - 1] - 1 for index in range(1, 21))
            mean_return = _average(returns)
            variance = (
                sum(
                    ((value - mean_return) ** 2 for value in returns),
                    start=_ZERO,
                )
                / _TWENTY
            )
            true_ranges = tuple(
                max(
                    inputs[index].high_price - inputs[index].low_price,
                    abs(inputs[index].high_price - close[index - 1]),
                    abs(inputs[index].low_price - close[index - 1]),
                )
                for index in range(7, 21)
            )
            values: dict[str, object] = {
                "last_close": close[20],
                "one_day_return": close[20] / close[19] - 1,
                "five_day_return": close[20] / close[15] - 1,
                "twenty_day_return": close[20] / close[0] - 1,
                "latest_gap_return": inputs[20].open_price / close[19] - 1,
                "latest_intraday_return": close[20] / inputs[20].open_price - 1,
                "latest_range_rate": (inputs[20].high_price - inputs[20].low_price) / close[19],
                "close_vs_sma5": close[20] / _average(close[16:21]) - 1,
                "close_vs_sma10": close[20] / _average(close[11:21]) - 1,
                "close_vs_sma20": close[20] / _average(close[1:21]) - 1,
                "realized_volatility_20d": variance.sqrt(),
                "atr14_rate": _average(true_ranges) / close[20],
                "distance_from_prior_20d_high": (
                    close[20] / max(bar.high_price for bar in inputs[:20]) - 1
                ),
                "distance_from_prior_20d_low": (
                    close[20] / min(bar.low_price for bar in inputs[:20]) - 1
                ),
                "adjustment_basis": DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED.value,
                "completed_bar_count": 21,
            }
            quality, reasons = _volume_features(inputs, values)
        return values, quality, reasons


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise DailyTechnicalFeatureBuildError("평균 계산 입력은 비어 있을 수 없습니다.")
    return sum(values, start=_ZERO) / Decimal(len(values))


def _volume_features(
    bars: tuple[DailyMarketBarInput, ...],
    values: dict[str, object],
) -> tuple[FeatureQualityStatus, tuple[str, ...]]:
    volumes = tuple(bar.volume for bar in bars)
    values.update(
        volume_ratio_5_to_20=None,
        latest_volume_to_avg20=None,
        average_dollar_volume_20=None,
    )
    if any(volume is None for volume in volumes):
        return FeatureQualityStatus.DEGRADED, ("VOLUME_DATA_INCOMPLETE",)
    exact = tuple(Decimal(volume) for volume in volumes if volume is not None)
    average_20 = _average(exact[1:21])
    if average_20 == 0:
        return FeatureQualityStatus.DEGRADED, ("VOLUME_DATA_UNUSABLE",)
    values["volume_ratio_5_to_20"] = _average(exact[16:21]) / average_20
    values["latest_volume_to_avg20"] = exact[20] / average_20
    values["average_dollar_volume_20"] = _average(
        tuple(bars[index].close_price * exact[index] for index in range(1, 21))
    )
    return FeatureQualityStatus.READY, ()
