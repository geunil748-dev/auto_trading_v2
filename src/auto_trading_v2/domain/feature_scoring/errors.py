"""Sanitized validation failures for transparent relative scoring."""


class FeatureScoringValidationError(ValueError):
    """A categorical P4A contract violation without raw feature payloads."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)
