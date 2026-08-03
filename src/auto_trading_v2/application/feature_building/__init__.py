"""Deterministic daily technical feature calculation contracts."""

from auto_trading_v2.application.feature_building.contracts import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    INSUFFICIENT_REASON,
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalCalculationResult,
    DailyTechnicalFeatureSnapshotBuildOutcome,
    DailyTechnicalFeatureSnapshotBuildResult,
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
    "BuildDailyTechnicalFeatureSnapshotCommand",
    "DailyTechnicalCalculationOutcome",
    "DailyTechnicalCalculationResult",
    "DailyTechnicalFeatureBuildError",
    "DailyTechnicalFeatureBuilder",
    "DailyTechnicalFeatureSnapshotBuildOutcome",
    "DailyTechnicalFeatureSnapshotBuildResult",
]
