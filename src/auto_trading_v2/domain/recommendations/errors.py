"""Recommendation-specific validation failures."""

from auto_trading_v2.domain.errors import ValidationError


class RecommendationValidationError(ValidationError):
    """A canonical Recommendation contract was rejected."""
