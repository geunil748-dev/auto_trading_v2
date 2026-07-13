"""Time boundary used by application and adapter code."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide current UTC time without coupling callers to wall-clock access."""

    def now_utc(self) -> datetime:
        """Return a timezone-aware UTC datetime."""
        ...
