"""Sanitized validation failures for P4B.2A datasets."""

from auto_trading_v2.domain.errors import ValidationError


class ProbabilityCalibrationDatasetValidationError(ValidationError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)
