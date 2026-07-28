"""Immutable creation contracts for canonical DailyMarketBar facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    DailyMarketBarValidationError,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    DailyMarketBarID,
    SessionDate,
    Symbol,
)


@dataclass(frozen=True, slots=True)
class CreateDailyMarketBarCommand:
    source_code: str
    source_record_key: str
    source_version: str
    symbol: Symbol
    currency: Currency
    adjustment_basis: DailyMarketBarAdjustmentBasis
    session_date: SessionDate
    observed_at: datetime
    available_at: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int | None
    _bar_input: DailyMarketBarInput = field(init=False, repr=False)

    def __post_init__(self) -> None:
        bar_input = DailyMarketBarInput(
            source_code=self.source_code,
            source_record_key=self.source_record_key,
            source_version=self.source_version,
            symbol=self.symbol,
            currency=self.currency,
            adjustment_basis=self.adjustment_basis,
            session_date=self.session_date,
            observed_at=self.observed_at,
            available_at=self.available_at,
            open_price=self.open_price,
            high_price=self.high_price,
            low_price=self.low_price,
            close_price=self.close_price,
            volume=self.volume,
        )
        object.__setattr__(self, "_bar_input", bar_input)
        for name in (
            "source_code",
            "source_record_key",
            "source_version",
            "symbol",
            "currency",
            "adjustment_basis",
            "session_date",
            "observed_at",
            "available_at",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        ):
            object.__setattr__(self, name, getattr(bar_input, name))

    @property
    def bar_input(self) -> DailyMarketBarInput:
        return self._bar_input


@dataclass(frozen=True, slots=True)
class NewDailyMarketBar:
    daily_market_bar_id: DailyMarketBarID
    bar_key: str
    content_digest: str
    bar_input: DailyMarketBarInput = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.daily_market_bar_id, DailyMarketBarID):
            raise DailyMarketBarValidationError("daily_market_bar_id 타입이 올바르지 않습니다.")
        if not isinstance(self.bar_input, DailyMarketBarInput):
            raise DailyMarketBarValidationError("bar_input 타입이 올바르지 않습니다.")
        if self.bar_key != daily_market_bar_key(self.bar_input):
            raise DailyMarketBarValidationError("bar_key가 semantic identity와 다릅니다.")
        if self.content_digest != daily_market_bar_content_digest(self.bar_input):
            raise DailyMarketBarValidationError("content_digest가 bar 내용과 다릅니다.")

    def stored(self, recorded_at: datetime) -> DailyMarketBar:
        return DailyMarketBar(
            daily_market_bar_id=self.daily_market_bar_id,
            bar_key=self.bar_key,
            content_digest=self.content_digest,
            bar_input=self.bar_input,
            recorded_at=recorded_at,
        )


class DailyMarketBarCreationOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class DailyMarketBarCreationResult:
    outcome: DailyMarketBarCreationOutcome
    bar: DailyMarketBar
