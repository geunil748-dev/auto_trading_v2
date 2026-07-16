"""Domain failures for pure position projection."""


class PositionProjectionValidationError(ValueError):
    """Projection inputs cannot produce a valid canonical position state."""
