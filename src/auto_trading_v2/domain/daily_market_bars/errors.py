"""Sanitized validation failures for canonical daily market bars."""

from auto_trading_v2.domain.errors import ValidationError


class DailyMarketBarValidationError(ValidationError):
    """Raised when a DailyMarketBar contract violates canonical policy."""
