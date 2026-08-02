"""Typed identifier generation adapters."""

from auto_trading_v2.adapters.identifiers.uuid_factory import (
    Uuid5ClientOrderIDFactory,
    UuidDailyFeaturePipelineItemIDFactory,
    UuidDailyFeaturePipelineRunIDFactory,
    UuidDailyFeatureScoringItemIDFactory,
    UuidDailyFeatureScoringRunIDFactory,
    UuidDailyMarketBarIDFactory,
    UuidDecisionIDFactory,
    UuidFeatureSnapshotIDFactory,
    UuidFillIDFactory,
    UuidFilterEvaluationIDFactory,
    UuidOrderIDFactory,
    UuidPositionEventIDFactory,
    UuidPositionIDFactory,
    UuidRecommendationIDFactory,
    UuidTradeIntentIDFactory,
    UuidUniverseSnapshotIDFactory,
)

__all__ = [
    "Uuid5ClientOrderIDFactory",
    "UuidDailyFeaturePipelineItemIDFactory",
    "UuidDailyFeaturePipelineRunIDFactory",
    "UuidDailyFeatureScoringItemIDFactory",
    "UuidDailyFeatureScoringRunIDFactory",
    "UuidDailyMarketBarIDFactory",
    "UuidDecisionIDFactory",
    "UuidFilterEvaluationIDFactory",
    "UuidFeatureSnapshotIDFactory",
    "UuidFillIDFactory",
    "UuidOrderIDFactory",
    "UuidPositionEventIDFactory",
    "UuidPositionIDFactory",
    "UuidRecommendationIDFactory",
    "UuidTradeIntentIDFactory",
    "UuidUniverseSnapshotIDFactory",
]
