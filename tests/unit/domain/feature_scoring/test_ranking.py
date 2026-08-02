from decimal import Decimal

from auto_trading_v2.domain.feature_scoring import (
    CalculatedComponentScores,
    RankingInput,
    deterministic_ranks,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import Symbol


def scores(overall: str, momentum: str = "50", trend: str = "50") -> CalculatedComponentScores:
    return CalculatedComponentScores(
        Decimal(momentum),
        Decimal(trend),
        Decimal("50"),
        Decimal("50"),
        Decimal("50"),
        Decimal("50"),
        Decimal(overall),
    )


def entry(
    key: str,
    quality: FeatureQualityStatus,
    overall: str,
    *,
    momentum: str = "50",
    trend: str = "50",
    mic: str = "XNGS",
    symbol: str | None = None,
) -> RankingInput:
    return RankingInput(key, quality, mic, Symbol(symbol or key), scores(overall, momentum, trend))


def test_quality_tier_precedes_score_and_rank_is_unique_sequential() -> None:
    ranks = deterministic_ranks(
        (
            entry("NVDA", FeatureQualityStatus.DEGRADED, "100"),
            entry("AAPL", FeatureQualityStatus.READY, "10"),
            entry("MSFT", FeatureQualityStatus.READY, "90"),
        )
    )

    assert ranks == {"MSFT": 1, "AAPL": 2, "NVDA": 3}


def test_tie_breakers_are_overall_momentum_trend_mic_symbol() -> None:
    values = (
        entry("E", FeatureQualityStatus.READY, "50", symbol="ZZZ"),
        entry("D", FeatureQualityStatus.READY, "50", mic="XNYS", symbol="AAA"),
        entry("C", FeatureQualityStatus.READY, "50", trend="60"),
        entry("B", FeatureQualityStatus.READY, "50", momentum="60"),
        entry("A", FeatureQualityStatus.READY, "60"),
    )

    assert deterministic_ranks(values) == {"A": 1, "B": 2, "C": 3, "E": 4, "D": 5}
    assert deterministic_ranks(tuple(reversed(values))) == deterministic_ranks(values)
