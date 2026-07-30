"""Immutable read-only cross-provider daily-bar comparison contract."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from auto_trading_v2.domain.daily_market_bars import DailyMarketBarValidationError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc

_SOURCE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class DailyBarProviderComparisonOutcome(StrEnum):
    COMPARABLE = "COMPARABLE"
    INSUFFICIENT_OVERLAP = "INSUFFICIENT_OVERLAP"
    PRIMARY_DATA_MISSING = "PRIMARY_DATA_MISSING"
    VALIDATION_DATA_MISSING = "VALIDATION_DATA_MISSING"


@dataclass(frozen=True, slots=True)
class CompareDailyBarProvidersCommand:
    primary_source_code: str
    validation_source_code: str
    symbol: Symbol
    as_of: datetime
    requested_session_count: int
    minimum_overlap_sessions: int

    def __post_init__(self) -> None:
        primary = _source(self.primary_source_code)
        validation = _source(self.validation_source_code)
        if primary == validation:
            raise DailyMarketBarValidationError("provider source codes must be distinct")
        if not isinstance(self.symbol, Symbol):
            raise DailyMarketBarValidationError("symbol must be valid")
        try:
            as_of = normalize_utc(self.as_of)
        except ValidationError:
            raise DailyMarketBarValidationError("as_of must be timezone-aware") from None
        if (
            isinstance(self.requested_session_count, bool)
            or not isinstance(self.requested_session_count, int)
            or self.requested_session_count < 1
        ):
            raise DailyMarketBarValidationError("requested_session_count must be positive")
        if (
            isinstance(self.minimum_overlap_sessions, bool)
            or not isinstance(self.minimum_overlap_sessions, int)
            or not 1 <= self.minimum_overlap_sessions <= self.requested_session_count
        ):
            raise DailyMarketBarValidationError("minimum_overlap_sessions is invalid")
        object.__setattr__(self, "primary_source_code", primary)
        object.__setattr__(self, "validation_source_code", validation)
        object.__setattr__(self, "as_of", as_of)


@dataclass(frozen=True, slots=True)
class DailyBarProviderComparisonReport:
    outcome: DailyBarProviderComparisonOutcome
    primary_source_code: str
    validation_source_code: str
    symbol: Symbol
    as_of: datetime
    primary_bar_count: int
    validation_bar_count: int
    overlap_count: int
    primary_only_session_count: int
    validation_only_session_count: int
    median_absolute_close_relative_difference: Decimal | None
    maximum_absolute_close_relative_difference: Decimal | None
    return_direction_agreement_count: int
    return_direction_observation_count: int
    return_direction_agreement_rate: Decimal | None


def _source(value: object) -> str:
    if not isinstance(value, str):
        raise DailyMarketBarValidationError("source code must be text")
    normalized = value.strip()
    if not _SOURCE_CODE.fullmatch(normalized):
        raise DailyMarketBarValidationError("source code format is invalid")
    return normalized
