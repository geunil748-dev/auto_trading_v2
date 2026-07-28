"""Payload-safe application errors for Recommendation creation."""

from auto_trading_v2.domain.primitives import FeatureSnapshotID


class RecommendationConflictError(RuntimeError):
    """The semantic identity exists with different canonical content."""

    def __init__(self, recommendation_key: str) -> None:
        self.recommendation_key = recommendation_key
        super().__init__(f"recommendation content conflict: {recommendation_key}")


class RecommendationRaceResolutionError(RuntimeError):
    """A unique-write race could not be resolved to a canonical row."""

    def __init__(self) -> None:
        super().__init__("recommendation write race could not be resolved")


class RecommendationSourceNotFoundError(RuntimeError):
    """The referenced FeatureSnapshot does not exist."""

    def __init__(self, feature_snapshot_id: FeatureSnapshotID) -> None:
        self.feature_snapshot_id = feature_snapshot_id
        super().__init__(f"feature snapshot not found: {feature_snapshot_id}")


class RecommendationSourceRejectedError(RuntimeError):
    """The source snapshot cannot support the requested recommendation."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"recommendation source rejected: {reason}")
