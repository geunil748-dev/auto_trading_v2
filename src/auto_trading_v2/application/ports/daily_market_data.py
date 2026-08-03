"""Provider-neutral port for future completed daily market data adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import SessionDate, Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc

_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MIC_PATTERN = re.compile(r"^[A-Z0-9]{4}$")
type CompletedDailyMarketBarObservation = DailyMarketBarInput


@dataclass(frozen=True, slots=True)
class DailyMarketDataProviderCapabilities:
    """Explicit provider behavior used without automatic fallback."""

    provider_code: str
    official: bool
    requires_api_key: bool
    supports_raw_daily_bars: bool
    supports_split_adjusted_daily_bars: bool
    supports_adjusted_volume: bool
    supports_completed_cutoff: bool
    supports_pagination: bool
    maximum_rows_per_request: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.provider_code, str):
            raise DailyMarketBarValidationError("provider_code 타입이 올바르지 않습니다.")
        provider_code = self.provider_code.strip()
        if not _CODE_PATTERN.fullmatch(provider_code):
            raise DailyMarketBarValidationError("provider_code 형식이 올바르지 않습니다.")
        for name in (
            "official",
            "requires_api_key",
            "supports_raw_daily_bars",
            "supports_split_adjusted_daily_bars",
            "supports_adjusted_volume",
            "supports_completed_cutoff",
            "supports_pagination",
        ):
            if not isinstance(getattr(self, name), bool):
                raise DailyMarketBarValidationError(f"{name} 타입이 올바르지 않습니다.")
        maximum = self.maximum_rows_per_request
        if maximum is not None and (
            isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1
        ):
            raise DailyMarketBarValidationError(
                "maximum_rows_per_request는 1 이상 또는 None이어야 합니다."
            )
        object.__setattr__(self, "provider_code", provider_code)


@dataclass(frozen=True, slots=True)
class FetchCompletedDailyBarsRequest:
    source_code: str
    symbol: Symbol
    adjustment_basis: DailyMarketBarAdjustmentBasis
    as_of: datetime
    requested_session_count: int
    mic_code: str | None = None
    completed_through_session_date: SessionDate | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_code, str):
            raise DailyMarketBarValidationError("source_code 타입이 올바르지 않습니다.")
        source_code = self.source_code.strip()
        if not _CODE_PATTERN.fullmatch(source_code):
            raise DailyMarketBarValidationError("source_code 형식이 올바르지 않습니다.")
        if not isinstance(self.symbol, Symbol):
            raise DailyMarketBarValidationError("symbol 타입이 올바르지 않습니다.")
        if not isinstance(self.adjustment_basis, DailyMarketBarAdjustmentBasis):
            raise DailyMarketBarValidationError("adjustment_basis 타입이 올바르지 않습니다.")
        if (
            isinstance(self.requested_session_count, bool)
            or not isinstance(self.requested_session_count, int)
            or self.requested_session_count < 1
        ):
            raise DailyMarketBarValidationError("requested_session_count는 1 이상이어야 합니다.")
        try:
            as_of = normalize_utc(self.as_of)
        except ValidationError:
            raise DailyMarketBarValidationError(
                "as_of는 timezone-aware datetime이어야 합니다."
            ) from None
        object.__setattr__(self, "source_code", source_code)
        object.__setattr__(self, "as_of", as_of)
        if self.mic_code is not None:
            if not isinstance(self.mic_code, str):
                raise DailyMarketBarValidationError("mic_code 타입이 올바르지 않습니다.")
            mic_code = self.mic_code.strip().upper()
            if not _MIC_PATTERN.fullmatch(mic_code):
                raise DailyMarketBarValidationError("mic_code 형식이 올바르지 않습니다.")
            object.__setattr__(self, "mic_code", mic_code)
        if self.completed_through_session_date is not None and not isinstance(
            self.completed_through_session_date,
            SessionDate,
        ):
            raise DailyMarketBarValidationError(
                "completed_through_session_date 타입이 올바르지 않습니다."
            )


class DailyMarketDataProvider(Protocol):
    @property
    def capabilities(self) -> DailyMarketDataProviderCapabilities: ...

    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[CompletedDailyMarketBarObservation, ...]: ...
