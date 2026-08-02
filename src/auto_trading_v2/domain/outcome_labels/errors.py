"""Sanitized validation failures for P4B.2A outcome labels."""

from auto_trading_v2.domain.errors import ValidationError


class OutcomeLabelValidationError(ValidationError):
    """Expose only a stable technical category."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)
