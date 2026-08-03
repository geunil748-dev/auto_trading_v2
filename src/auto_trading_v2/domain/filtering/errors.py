"""Safe domain errors for deterministic filter evaluation."""

from auto_trading_v2.domain.errors import ValidationError


class FilterValidationError(ValidationError):
    """A filter input, definition, or result violates its contract."""
