"""Stable position projection states and outcomes."""

from enum import StrEnum


class PaperPositionStatus(StrEnum):
    """Canonical current PaperPosition states defined by the schema."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PositionEventType(StrEnum):
    """BUY-side PositionEvent types supported by this projector."""

    OPENED = "OPENED"
    INCREASED = "INCREASED"


class ProjectionOutcome(StrEnum):
    """Public result category for one Fill projection request."""

    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
