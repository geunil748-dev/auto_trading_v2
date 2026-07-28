"""Safe validation failures for deterministic feature calculation."""

from auto_trading_v2.domain.errors import ValidationError


class DailyTechnicalFeatureBuildError(ValidationError):
    """Raised when bar inputs violate the fixed v1 feature contract."""
