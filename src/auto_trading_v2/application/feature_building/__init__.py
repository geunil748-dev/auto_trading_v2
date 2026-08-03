"""Deterministic daily technical feature calculation contracts."""

from auto_trading_v2.application.feature_building.contracts import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    INSUFFICIENT_REASON,
    PRICE_ONLY_FEATURE_SET_CODE,
    PRICE_ONLY_FEATURE_SET_VERSION,
    BuildDailyPriceTechnicalFeatureSnapshotCommand,
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalCalculationResult,
    DailyTechnicalFeatureSnapshotBuildOutcome,
    DailyTechnicalFeatureSnapshotBuildResult,
)
from auto_trading_v2.application.feature_building.daily_price_technical_v2 import (
    PRICE_FEATURE_NAMES,
    PRICE_ONLY_METADATA_NAMES,
    DailyPriceTechnicalFeatureBuilderV2,
)
from auto_trading_v2.application.feature_building.daily_technical import (
    DailyTechnicalFeatureBuilder,
)
from auto_trading_v2.application.feature_building.errors import (
    DailyTechnicalFeatureBuildError,
)

__all__ = [
    "FEATURE_SET_CODE",
    "FEATURE_SET_VERSION",
    "INSUFFICIENT_REASON",
    "PRICE_FEATURE_NAMES",
    "PRICE_ONLY_FEATURE_SET_CODE",
    "PRICE_ONLY_FEATURE_SET_VERSION",
    "PRICE_ONLY_METADATA_NAMES",
    "BuildDailyPriceTechnicalFeatureSnapshotCommand",
    "BuildDailyTechnicalFeatureSnapshotCommand",
    "DailyTechnicalCalculationOutcome",
    "DailyTechnicalCalculationResult",
    "DailyTechnicalFeatureBuildError",
    "DailyTechnicalFeatureBuilder",
    "DailyPriceTechnicalFeatureBuilderV2",
    "DailyTechnicalFeatureSnapshotBuildOutcome",
    "DailyTechnicalFeatureSnapshotBuildResult",
]
