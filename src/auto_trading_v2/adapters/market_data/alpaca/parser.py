"""Strict immutable mapping of Alpaca single-stock daily bar pages."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from auto_trading_v2.adapters.market_data.alpaca.errors import (
    AlpacaErrorCategory,
    AlpacaProviderError,
)
from auto_trading_v2.application.ports.daily_market_data import (
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
)
from auto_trading_v2.domain.primitives import Currency, SessionDate
from auto_trading_v2.domain.primitives.time import normalize_utc

ALPACA_SOURCE_CODE = "ALPACA_IEX_STOCK_BARS"
ALPACA_SOURCE_FEED = "iex"
_MAPPING_VERSION = "alpaca-stock-bars-v1"
_NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class AlpacaBarPage:
    bars: tuple[DailyMarketBarInput, ...]
    next_page_token: str | None


class AlpacaStockBarsParser:
    def parse_page(
        self,
        payload: object,
        request: FetchCompletedDailyBarsRequest,
        observed_at: datetime,
    ) -> AlpacaBarPage:
        body = _mapping(payload)
        symbol = body.get("symbol")
        if not isinstance(symbol, str) or symbol.strip().upper() != request.symbol.value:
            raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID)
        raw_bars = body.get("bars")
        if not isinstance(raw_bars, list):
            raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID)
        cutoff = request.completed_through_session_date
        if cutoff is None:
            raise AlpacaProviderError(AlpacaErrorCategory.CONFIGURATION_INVALID)
        observed = normalize_utc(observed_at)
        parsed: list[DailyMarketBarInput] = []
        seen: set[date] = set()
        for raw in raw_bars:
            row = _mapping(raw)
            session = _session_date(row.get("t"))
            if session in seen:
                raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
            seen.add(session)
            open_price = _price(row.get("o"))
            high_price = _price(row.get("h"))
            low_price = _price(row.get("l"))
            close_price = _price(row.get("c"))
            volume = _volume(row.get("v"))
            _optional_trade_count(row.get("n"))
            _optional_vwap(row.get("vw"))
            if high_price < max(open_price, low_price, close_price):
                raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
            if low_price > min(open_price, high_price, close_price):
                raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
            if session <= cutoff.value:
                parsed.append(
                    _bar(
                        request,
                        observed,
                        session,
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                        volume,
                    )
                )
        parsed.sort(key=lambda item: item.session_date.value)
        return AlpacaBarPage(tuple(parsed), _page_token(body.get("next_page_token")))


def _bar(
    request: FetchCompletedDailyBarsRequest,
    observed_at: datetime,
    session: date,
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
    volume: int,
) -> DailyMarketBarInput:
    mic_code = request.mic_code
    if mic_code is None:
        raise AlpacaProviderError(AlpacaErrorCategory.CONFIGURATION_INVALID)
    adjustment = (
        "SPLIT"
        if request.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
        else "RAW"
    )
    version = _source_version(
        request.symbol.value,
        mic_code,
        adjustment,
        session,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
    )
    return DailyMarketBarInput(
        source_code=ALPACA_SOURCE_CODE,
        source_record_key=(
            f"{mic_code}.{request.symbol.value}.{session.strftime('%Y%m%d')}.IEX.{adjustment}"
        ),
        source_version=version,
        symbol=request.symbol,
        currency=Currency("USD"),
        adjustment_basis=request.adjustment_basis,
        session_date=SessionDate(session),
        observed_at=observed_at,
        available_at=observed_at,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
    )


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID)
    return value


def _session_date(value: object) -> date:
    if not isinstance(value, str) or not value.strip():
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        if parsed.utcoffset() != timedelta(0):
            raise ValueError
        normalized = normalize_utc(parsed)
    except (ValueError, TypeError):
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID) from None
    return _new_york_date(normalized)


def _new_york_date(value: datetime) -> date:
    return value.astimezone(_NEW_YORK).date()


def _price(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed <= 0:
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
    return parsed


def _volume(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
    return value


def _optional_trade_count(value: object) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)


def _optional_vwap(value: object) -> None:
    if value is not None:
        _price(value)


def _page_token(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AlpacaProviderError(AlpacaErrorCategory.PAGINATION_INVALID)
    token = value.strip()
    if not token:
        return None
    if len(token) > 2048 or any(ord(character) < 32 for character in token):
        raise AlpacaProviderError(AlpacaErrorCategory.PAGINATION_INVALID)
    return token


def _source_version(
    symbol: str,
    mic_code: str,
    adjustment: str,
    session: date,
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
    volume: int,
) -> str:
    content = {
        "adjustment": adjustment,
        "close": _decimal_text(close_price),
        "feed": ALPACA_SOURCE_FEED,
        "high": _decimal_text(high_price),
        "low": _decimal_text(low_price),
        "mapping_version": _MAPPING_VERSION,
        "mic_code": mic_code,
        "open": _decimal_text(open_price),
        "session_date": session.isoformat(),
        "symbol": symbol,
        "volume": volume,
    }
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
