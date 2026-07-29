"""Immutable commands and safe summaries for Twelve Data ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from auto_trading_v2.application.feature_building import (
    DailyTechnicalFeatureSnapshotBuildResult,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import SessionDate, Symbol

_SUPPORTED_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})
_SAFE_CATEGORY = re.compile(r"^[A-Z0-9_]{1,96}$")


@dataclass(frozen=True, slots=True)
class TwelveDataDailyMarketBarIngestionCommand:
    symbol: Symbol
    mic_code: str
    adjustment_basis: DailyMarketBarAdjustmentBasis
    completed_through_session_date: SessionDate
    requested_session_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise DailyMarketBarValidationError("symbol 타입이 올바르지 않습니다.")
        if not isinstance(self.mic_code, str):
            raise DailyMarketBarValidationError("mic_code 타입이 올바르지 않습니다.")
        mic_code = self.mic_code.strip().upper()
        if mic_code not in _SUPPORTED_MICS:
            raise DailyMarketBarValidationError("지원하지 않는 미국 MIC입니다.")
        if not isinstance(self.adjustment_basis, DailyMarketBarAdjustmentBasis):
            raise DailyMarketBarValidationError("adjustment_basis 타입이 올바르지 않습니다.")
        if not isinstance(self.completed_through_session_date, SessionDate):
            raise DailyMarketBarValidationError(
                "completed_through_session_date 타입이 올바르지 않습니다."
            )
        if (
            isinstance(self.requested_session_count, bool)
            or not isinstance(self.requested_session_count, int)
            or not 1 <= self.requested_session_count <= 5000
        ):
            raise DailyMarketBarValidationError(
                "requested_session_count는 1 이상 5000 이하여야 합니다."
            )
        object.__setattr__(self, "mic_code", mic_code)


class TwelveDataIngestionOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_EXISTING = "COMPLETED_WITH_EXISTING"
    NO_DATA = "NO_DATA"
    PROVIDER_DISABLED = "PROVIDER_DISABLED"
    PROVIDER_CONFIGURATION_MISSING = "PROVIDER_CONFIGURATION_MISSING"
    CREDIT_BUDGET_EXHAUSTED = "CREDIT_BUDGET_EXHAUSTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INGESTION_CONFLICT = "INGESTION_CONFLICT"


@dataclass(frozen=True, slots=True)
class TwelveDataIngestionSummary:
    provider_code: str
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
        counts = (self.fetched_count, self.created_count, self.existing_count)
        invalid = any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts
        )
        if invalid:
            raise DailyMarketBarValidationError("ingestion count가 올바르지 않습니다.")
        if self.safe_error_category is not None and not _SAFE_CATEGORY.fullmatch(
            self.safe_error_category
        ):
            raise DailyMarketBarValidationError("safe_error_category 형식이 올바르지 않습니다.")


@dataclass(frozen=True, slots=True)
class TwelveDataIngestionResult:
    outcome: TwelveDataIngestionOutcome
    summary: TwelveDataIngestionSummary
    bars: tuple[DailyMarketBar, ...] = ()


@dataclass(frozen=True, slots=True)
class TwelveDataDailyFeatureCommand:
    ingestion: TwelveDataDailyMarketBarIngestionCommand
    horizon: TradingDayHorizon

    def __post_init__(self) -> None:
        if not isinstance(self.ingestion, TwelveDataDailyMarketBarIngestionCommand):
            raise DailyMarketBarValidationError("ingestion command가 필요합니다.")
        if not isinstance(self.horizon, TradingDayHorizon):
            raise DailyMarketBarValidationError("horizon 타입이 올바르지 않습니다.")


@dataclass(frozen=True, slots=True)
class TwelveDataDailyFeatureResult:
    ingestion: TwelveDataIngestionResult
    feature_snapshot: DailyTechnicalFeatureSnapshotBuildResult | None
