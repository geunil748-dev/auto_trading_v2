"""Immutable provider-neutral completed daily market bars."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from auto_trading_v2.domain.daily_market_bars.errors import (
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    Currency,
    DailyMarketBarID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc

_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_RECORD_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_BAR_KEY_PATTERN = re.compile(r"^daily-market-bar:v1:[0-9a-f]{64}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_PRICE_FIELDS = ("open_price", "high_price", "low_price", "close_price")


class DailyMarketBarAdjustmentBasis(StrEnum):
    """Persistable provider adjustment policy."""

    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"


@dataclass(frozen=True, slots=True)
class DailyMarketBarInput:
    """Validated canonical content independent of persistence and providers."""

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

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_code", _code(self.source_code, "source_code"))
        object.__setattr__(self, "source_record_key", _record_key(self.source_record_key))
        object.__setattr__(self, "source_version", _code(self.source_version, "source_version"))
        if not isinstance(self.symbol, Symbol):
            raise DailyMarketBarValidationError("symbol 타입이 올바르지 않습니다.")
        if not isinstance(self.currency, Currency) or self.currency.code != "USD":
            raise DailyMarketBarValidationError("DailyMarketBar 통화는 USD여야 합니다.")
        if not isinstance(self.adjustment_basis, DailyMarketBarAdjustmentBasis):
            raise DailyMarketBarValidationError("adjustment_basis 타입이 올바르지 않습니다.")
        if not isinstance(self.session_date, SessionDate):
            raise DailyMarketBarValidationError("session_date 타입이 올바르지 않습니다.")
        observed_at = _timestamp(self.observed_at, "observed_at")
        available_at = _timestamp(self.available_at, "available_at")
        if observed_at > available_at:
            raise DailyMarketBarValidationError("observed_at은 available_at 이후일 수 없습니다.")
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "available_at", available_at)
        for name in _PRICE_FIELDS:
            _positive_decimal(getattr(self, name), name)
        if self.high_price < self.low_price:
            raise DailyMarketBarValidationError("high_price는 low_price보다 작을 수 없습니다.")
        if self.high_price < self.open_price or self.high_price < self.close_price:
            raise DailyMarketBarValidationError("high_price가 open/close보다 작습니다.")
        if self.low_price > self.open_price or self.low_price > self.close_price:
            raise DailyMarketBarValidationError("low_price가 open/close보다 큽니다.")
        if self.volume is not None and (
            isinstance(self.volume, bool) or not isinstance(self.volume, int) or self.volume < 0
        ):
            raise DailyMarketBarValidationError("volume은 0 이상 정수 또는 None이어야 합니다.")


@dataclass(frozen=True, slots=True)
class DailyMarketBar:
    """Canonical immutable stored daily bar."""

    daily_market_bar_id: DailyMarketBarID
    bar_key: str
    content_digest: str
    bar_input: DailyMarketBarInput = field(repr=False)
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.daily_market_bar_id, DailyMarketBarID):
            raise DailyMarketBarValidationError("daily_market_bar_id 타입이 올바르지 않습니다.")
        if not isinstance(self.bar_input, DailyMarketBarInput):
            raise DailyMarketBarValidationError("bar_input 타입이 올바르지 않습니다.")
        if not _BAR_KEY_PATTERN.fullmatch(self.bar_key):
            raise DailyMarketBarValidationError("bar_key 형식이 올바르지 않습니다.")
        if not _DIGEST_PATTERN.fullmatch(self.content_digest):
            raise DailyMarketBarValidationError("content_digest 형식이 올바르지 않습니다.")
        if self.bar_key != daily_market_bar_key(self.bar_input):
            raise DailyMarketBarValidationError("bar_key가 semantic identity와 다릅니다.")
        if self.content_digest != daily_market_bar_content_digest(self.bar_input):
            raise DailyMarketBarValidationError("content_digest가 bar 내용과 다릅니다.")
        object.__setattr__(self, "recorded_at", _timestamp(self.recorded_at, "recorded_at"))


def daily_market_bar_key(bar_input: DailyMarketBarInput) -> str:
    """Derive a stable key from provider semantic identity only."""

    identity = {
        "source_code": bar_input.source_code,
        "source_record_key": bar_input.source_record_key,
        "source_version": bar_input.source_version,
    }
    return f"daily-market-bar:v1:{_sha256(_canonical_json(identity))}"


def daily_market_bar_content_digest(bar_input: DailyMarketBarInput) -> str:
    """Hash normalized immutable market content without database-owned fields."""

    content = {
        "adjustment_basis": bar_input.adjustment_basis.value,
        "available_at": UtcTimestamp(bar_input.available_at).serialize(),
        "close": _decimal_text(bar_input.close_price),
        "currency": bar_input.currency.code,
        "high": _decimal_text(bar_input.high_price),
        "low": _decimal_text(bar_input.low_price),
        "observed_at": UtcTimestamp(bar_input.observed_at).serialize(),
        "open": _decimal_text(bar_input.open_price),
        "session_date": bar_input.session_date.serialize(),
        "symbol": bar_input.symbol.serialize(),
        "volume": bar_input.volume,
    }
    return _sha256(_canonical_json(content))


def _code(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise DailyMarketBarValidationError(f"{label} 타입이 올바르지 않습니다.")
    normalized = value.strip()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise DailyMarketBarValidationError(f"{label} 형식이 올바르지 않습니다.")
    return normalized


def _record_key(value: str) -> str:
    if not isinstance(value, str):
        raise DailyMarketBarValidationError("source_record_key 타입이 올바르지 않습니다.")
    normalized = value.strip()
    if not _RECORD_KEY_PATTERN.fullmatch(normalized):
        raise DailyMarketBarValidationError("source_record_key는 안전한 불투명 기술 키여야 합니다.")
    return normalized


def _timestamp(value: datetime, label: str) -> datetime:
    try:
        return normalize_utc(value)
    except ValidationError:
        raise DailyMarketBarValidationError(
            f"{label}은 timezone-aware datetime이어야 합니다."
        ) from None


def _positive_decimal(value: object, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise DailyMarketBarValidationError(f"{label}은 유한한 Decimal이어야 합니다.")
    if value <= 0:
        raise DailyMarketBarValidationError(f"{label}은 0보다 커야 합니다.")


def _decimal_text(value: Decimal) -> str:
    return "0" if value == 0 else format(value.normalize(), "f")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
