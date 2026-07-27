"""Canonical Recommendation domain contracts."""

from auto_trading_v2.domain.recommendations.errors import (
    RecommendationValidationError,
)
from auto_trading_v2.domain.recommendations.models import (
    Recommendation,
    RecommendationInput,
    recommendation_content_digest,
    recommendation_key,
    validate_generated_at,
)
from auto_trading_v2.domain.recommendations.plans import (
    RecommendationDisposition,
    RecommendationPlan,
)

__all__ = [
    "Recommendation",
    "RecommendationDisposition",
    "RecommendationInput",
    "RecommendationPlan",
    "RecommendationValidationError",
    "recommendation_content_digest",
    "recommendation_key",
    "validate_generated_at",
]
