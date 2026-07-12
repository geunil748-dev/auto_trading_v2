"""Time boundary used by application and adapter code."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime:
        """Return a timezone-aware UTC datetime."""
        ...
