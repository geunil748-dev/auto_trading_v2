"""Immutable commands and safe summaries for Alpaca validation ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.primitives import SessionDate, Symbol

_SUPPORTED_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})
_SAFE_CATEGORY = re.compile(r"^[A-Z0-9_]{1,96}$")


@dataclass(frozen=True, slots=True)
class AlpacaDailyMarketBarIngestionCommand:
    symbol: Symbol
    mic_code: str
    adjustment_basis: DailyMarketBarAdjustmentBasis
    completed_through_session_date: SessionDate
    requested_session_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise DailyMarketBarValidationError("symbol must be valid")
        if not isinstance(self.mic_code, str):
            raise DailyMarketBarValidationError("mic_code must be text")
        mic_code = self.mic_code.strip().upper()
        if mic_code not in _SUPPORTED_MICS:
            raise DailyMarketBarValidationError("mic_code is not a supported US listing MIC")
        if not isinstance(self.adjustment_basis, DailyMarketBarAdjustmentBasis):
            raise DailyMarketBarValidationError("adjustment_basis must be valid")
        if not isinstance(self.completed_through_session_date, SessionDate):
            raise DailyMarketBarValidationError("completed cutoff must be SessionDate")
        if (
            isinstance(self.requested_session_count, bool)
            or not isinstance(self.requested_session_count, int)
            or not 1 <= self.requested_session_count <= 10_000
        ):
            raise DailyMarketBarValidationError("requested_session_count must be 1..10000")
        object.__setattr__(self, "mic_code", mic_code)


class AlpacaIngestionOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_EXISTING = "COMPLETED_WITH_EXISTING"
    NO_DATA = "NO_DATA"
    PROVIDER_DISABLED = "PROVIDER_DISABLED"
    PROVIDER_CONFIGURATION_MISSING = "PROVIDER_CONFIGURATION_MISSING"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INGESTION_CONFLICT = "INGESTION_CONFLICT"


@dataclass(frozen=True, slots=True)
class AlpacaIngestionSummary:
    provider_code: str
    source_feed: str
    symbol: Symbol
    mic_code: str
    adjustment_basis: DailyMarketBarAdjustmentBasis
    completed_through_session_date: SessionDate
    fetched_count: int
    created_count: int
    existing_count: int
    oldest_session_date: SessionDate | None
    newest_session_date: SessionDate | None
    safe_error_category: str | None = None

    def __post_init__(self) -> None:
        for value in (self.fetched_count, self.created_count, self.existing_count):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DailyMarketBarValidationError("ingestion counts must be non-negative")
        if self.source_feed != "iex":
            raise DailyMarketBarValidationError("source_feed must be iex")
        if self.safe_error_category is not None and not _SAFE_CATEGORY.fullmatch(
            self.safe_error_category
        ):
            raise DailyMarketBarValidationError("safe_error_category must be a safe code")


@dataclass(frozen=True, slots=True)
class AlpacaIngestionResult:
    outcome: AlpacaIngestionOutcome
    summary: AlpacaIngestionSummary
    bars: tuple[DailyMarketBar, ...] = ()
