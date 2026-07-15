"""Safe validation errors for deterministic paper fills."""

from auto_trading_v2.domain.errors import ValidationError


class PaperFillValidationError(ValidationError):
    """A fill policy input or fill value violates the domain contract."""


class PaperFillHistoryValidationError(PaperFillValidationError):
    """Stored fill history cannot safely drive the next fill."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"invalid paper fill history: {reason}")
