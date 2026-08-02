"""Sanitized validation errors for P4B.1 forward outcomes."""

from auto_trading_v2.domain.errors import ValidationError


class OutcomeObservationValidationError(ValidationError):
    """Expose only a stable technical category."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)
