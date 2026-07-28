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
from auto_trading_v2.domain.primitives import Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc

_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
type CompletedDailyMarketBarObservation = DailyMarketBarInput


@dataclass(frozen=True, slots=True)
class FetchCompletedDailyBarsRequest:
    source_code: str
    symbol: Symbol
    adjustment_basis: DailyMarketBarAdjustmentBasis
    as_of: datetime
    requested_session_count: int

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


class DailyMarketDataProvider(Protocol):
    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[CompletedDailyMarketBarObservation, ...]: ...
