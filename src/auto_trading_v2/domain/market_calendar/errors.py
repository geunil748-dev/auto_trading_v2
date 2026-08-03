"""Safe market-calendar validation failures."""

from __future__ import annotations

import re

from auto_trading_v2.domain.errors import ValidationError

_SAFE_CATEGORY = re.compile(r"^[A-Z0-9_]{1,96}$")


class MarketCalendarValidationError(ValidationError):
    """Calendar contract failure carrying only a safe technical category."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "CALENDAR_CONTRACT_INVALID",
    ) -> None:
        if not _SAFE_CATEGORY.fullmatch(category):
            raise ValueError("calendar error category must be a safe technical code")
        self.category = category
        super().__init__(message)
