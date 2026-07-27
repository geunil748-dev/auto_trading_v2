"""Safe domain errors for Point-in-Time FeatureSnapshot rules."""

from auto_trading_v2.domain.errors import ValidationError


class FeatureSnapshotValidationError(ValidationError):
    """Raised when snapshot input cannot form a safe Point-in-Time record."""
