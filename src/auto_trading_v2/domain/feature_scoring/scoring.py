"""Decimal-only feature parsing, percentile scoring, and deterministic ranking."""

from __future__ import annotations

import re
from collections.abc import Hashable
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Never

from auto_trading_v2.domain.feature_scoring.errors import FeatureScoringValidationError
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, FeatureSnapshot
from auto_trading_v2.domain.primitives import Symbol

PRICE_FEATURE_GROUPS = {
    "momentum": ("one_day_return", "five_day_return", "twenty_day_return"),
    "trend": ("close_vs_sma5", "close_vs_sma10", "close_vs_sma20"),
    "breakout": ("distance_from_prior_20d_high", "distance_from_prior_20d_low"),
    "price_action": ("latest_gap_return", "latest_intraday_return"),
    "stability": ("latest_range_rate", "realized_volatility_20d", "atr14_rate"),
}
VOLUME_FEATURES = (
    "volume_ratio_5_to_20",
    "latest_volume_to_avg20",
    "average_dollar_volume_20",
)
REFERENCE_FEATURES = ("last_close", "completed_bar_count", "adjustment_basis")
REQUIRED_FEATURES = frozenset(
    (
        *REFERENCE_FEATURES,
        *(key for values in PRICE_FEATURE_GROUPS.values() for key in values),
        *VOLUME_FEATURES,
    )
)
SUPPORTED_DEGRADED_REASONS = frozenset({"VOLUME_DATA_INCOMPLETE", "VOLUME_DATA_UNUSABLE"})
DECIMAL_CONTEXT = Context(prec=38, rounding=ROUND_HALF_EVEN)
_DECIMAL_STRING = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


@dataclass(frozen=True, slots=True)
class ValidatedTechnicalFeatures:
    values: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class CalculatedComponentScores:
    momentum: Decimal
    trend: Decimal
    breakout: Decimal
    price_action: Decimal
    stability: Decimal
    volume: Decimal | None
    overall: Decimal


@dataclass(frozen=True, slots=True)
class RankingInput:
    key: Hashable
    quality_status: FeatureQualityStatus
    mic_code: str
    symbol: Symbol
    scores: CalculatedComponentScores


def parse_v1_technical_features(snapshot: FeatureSnapshot) -> ValidatedTechnicalFeatures:
    source = snapshot.snapshot_input
    if source.feature_set_code != "US_EQUITY_DAILY_TECHNICAL":
        _invalid("FEATURE_SET_CODE_MISMATCH")
    if source.feature_set_version != "v1":
        _invalid("FEATURE_SET_VERSION_MISMATCH")
    if set(source.feature_values) != REQUIRED_FEATURES:
        _invalid("FEATURE_KEY_CONTRACT_INVALID")
    if source.feature_values["adjustment_basis"] != "SPLIT_ADJUSTED":
        _invalid("FEATURE_ADJUSTMENT_BASIS_INVALID")
    count = source.feature_values["completed_bar_count"]
    if isinstance(count, bool) or count != 21:
        _invalid("FEATURE_COMPLETED_BAR_COUNT_INVALID")
    if source.quality_status is FeatureQualityStatus.READY:
        if any(source.feature_values[key] is None for key in VOLUME_FEATURES):
            _invalid("FEATURE_READY_VOLUME_INCOMPLETE")
    elif source.quality_status is FeatureQualityStatus.DEGRADED:
        if (
            len(source.quality_reason_codes) != 1
            or source.quality_reason_codes[0] not in SUPPORTED_DEGRADED_REASONS
        ):
            _invalid("FEATURE_QUALITY_UNSUPPORTED")
        if any(source.feature_values[key] is not None for key in VOLUME_FEATURES):
            _invalid("FEATURE_DEGRADED_VOLUME_SHAPE_INVALID")
    else:
        _invalid("FEATURE_QUALITY_UNSUPPORTED")
    values = {
        key: _decimal(source.feature_values[key], key)
        for key in REQUIRED_FEATURES - {"completed_bar_count", "adjustment_basis"}
        if key not in VOLUME_FEATURES or source.feature_values[key] is not None
    }
    return ValidatedTechnicalFeatures(values)


def ascending_midrank_percentiles[H: Hashable](
    values: dict[H, Decimal],
) -> dict[H, Decimal]:
    if not values:
        return {}
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in values.values()):
        _invalid("PERCENTILE_INPUT_INVALID")
    if len(values) == 1:
        return {next(iter(values)): Decimal("0.5")}
    ordered = sorted(values.items(), key=lambda pair: pair[1])
    result: dict[H, Decimal] = {}
    with localcontext(DECIMAL_CONTEXT):
        start = 0
        size = len(ordered)
        while start < size:
            end = start
            while end + 1 < size and ordered[end + 1][1] == ordered[start][1]:
                end += 1
            average_rank = (Decimal(start + 1) + Decimal(end + 1)) / Decimal(2)
            percentile = (average_rank - Decimal(1)) / Decimal(size - 1)
            for index in range(start, end + 1):
                result[ordered[index][0]] = percentile
            start = end + 1
    return result


def calculate_component_scores[H: Hashable](
    candidates: dict[H, ValidatedTechnicalFeatures],
    qualities: dict[H, FeatureQualityStatus],
) -> dict[H, CalculatedComponentScores]:
    if set(candidates) != set(qualities):
        _invalid("SCORING_POPULATION_MISMATCH")
    percentiles: dict[str, dict[H, Decimal]] = {}
    for feature in REQUIRED_FEATURES - set(REFERENCE_FEATURES) - set(VOLUME_FEATURES):
        percentiles[feature] = ascending_midrank_percentiles(
            {key: candidate.values[feature] for key, candidate in candidates.items()}
        )
    ready = {
        key: candidate
        for key, candidate in candidates.items()
        if qualities[key] is FeatureQualityStatus.READY
    }
    for feature in VOLUME_FEATURES:
        percentiles[feature] = ascending_midrank_percentiles(
            {key: candidate.values[feature] for key, candidate in ready.items()}
        )
    results: dict[H, CalculatedComponentScores] = {}
    with localcontext(DECIMAL_CONTEXT):
        for key in candidates:
            momentum = _component(percentiles, key, PRICE_FEATURE_GROUPS["momentum"])
            trend = _component(percentiles, key, PRICE_FEATURE_GROUPS["trend"])
            breakout = _component(percentiles, key, PRICE_FEATURE_GROUPS["breakout"])
            price_action = _component(percentiles, key, PRICE_FEATURE_GROUPS["price_action"])
            stability = _component(
                percentiles,
                key,
                PRICE_FEATURE_GROUPS["stability"],
                reverse=True,
            )
            volume = (
                _component(percentiles, key, VOLUME_FEATURES)
                if qualities[key] is FeatureQualityStatus.READY
                else None
            )
            active = [
                (momentum, 25),
                (trend, 25),
                (breakout, 20),
                (price_action, 10),
                (stability, 10),
            ]
            if volume is not None:
                active.append((volume, 10))
            overall = sum((score * weight for score, weight in active), Decimal(0)) / Decimal(
                sum(weight for _, weight in active)
            )
            results[key] = CalculatedComponentScores(
                momentum, trend, breakout, price_action, stability, volume, overall
            )
    return results


def deterministic_ranks(entries: tuple[RankingInput, ...]) -> dict[Hashable, int]:
    ordered = sorted(
        entries,
        key=lambda entry: (
            0 if entry.quality_status is FeatureQualityStatus.READY else 1,
            -entry.scores.overall,
            -entry.scores.momentum,
            -entry.scores.trend,
            entry.mic_code,
            entry.symbol.value,
        ),
    )
    return {entry.key: rank for rank, entry in enumerate(ordered, start=1)}


def _component[H: Hashable](
    percentiles: dict[str, dict[H, Decimal]],
    key: H,
    features: tuple[str, ...],
    *,
    reverse: bool = False,
) -> Decimal:
    values = tuple(percentiles[feature][key] for feature in features)
    if reverse:
        values = tuple(Decimal(1) - value for value in values)
    return sum(values, Decimal(0)) / Decimal(len(values)) * Decimal(100)


def _decimal(value: object, _feature: str) -> Decimal:
    if not isinstance(value, str) or not _DECIMAL_STRING.fullmatch(value):
        _invalid("FEATURE_NUMERIC_VALUE_INVALID")
    parsed = Decimal(value)
    if not parsed.is_finite():
        _invalid("FEATURE_NUMERIC_VALUE_INVALID")
    return parsed


def _invalid(category: str) -> Never:
    raise FeatureScoringValidationError(category)
