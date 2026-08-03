"""Validation errors for canonical paper-order values."""

from auto_trading_v2.domain.errors import ValidationError


class PaperOrderValidationError(ValidationError):
    """A paper-order state or reference violates its domain contract."""
