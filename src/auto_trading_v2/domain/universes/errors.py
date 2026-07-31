"""Sanitized validation failures for caller-provided universes."""

from __future__ import annotations

import re

from auto_trading_v2.domain.errors import ValidationError

_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class UniverseSnapshotValidationError(ValidationError):
    """Reject invalid universe content without retaining raw caller values."""

    def __init__(self, category: str = "UNIVERSE_INVALID") -> None:
        self.category = category if _CATEGORY.fullmatch(category) else "UNIVERSE_INVALID"
        super().__init__(f"UniverseSnapshot validation failed: {self.category}")
