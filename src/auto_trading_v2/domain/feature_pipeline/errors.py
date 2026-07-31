"""Sanitized daily feature pipeline validation failures."""

from __future__ import annotations

import re

from auto_trading_v2.domain.errors import ValidationError

_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")


class DailyFeaturePipelineValidationError(ValidationError):
    def __init__(self, category: str = "DAILY_FEATURE_PIPELINE_INVALID") -> None:
        self.category = (
            category if _CATEGORY.fullmatch(category) else "DAILY_FEATURE_PIPELINE_INVALID"
        )
        super().__init__(f"Daily feature pipeline validation failed: {self.category}")
