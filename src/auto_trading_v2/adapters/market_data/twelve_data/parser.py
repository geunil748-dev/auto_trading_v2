"""Strict immutable mapping of Twelve Data time_series responses."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from auto_trading_v2.adapters.market_data.twelve_data.errors import (
    TwelveDataErrorCategory,
    TwelveDataProviderError,
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

TWELVE_DATA_SOURCE_CODE = "TWELVE_DATA_TIME_SERIES"
_MAPPING_VERSION = "twelve-data-time-series-v1"
_EXPECTED_TIMEZONE = "America/New_York"


class TwelveDataTimeSeriesParser:
    def parse(
        self,
        payload: object,
        request: FetchCompletedDailyBarsRequest,
        observed_at: datetime,
    ) -> tuple[DailyMarketBarInput, ...]:
        body = _mapping(payload, TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)
        if body.get("status") != "ok":
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST)
        meta = _mapping(body.get("meta"), TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)
        _validate_meta(meta, request)
        values = body.get("values")
        if not isinstance(values, list):
            raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)
        observed = normalize_utc(observed_at)
        cutoff = request.completed_through_session_date
        if cutoff is None:
            raise TwelveDataProviderError(TwelveDataErrorCategory.CONFIGURATION_INVALID)
        rows: list[tuple[date, Decimal, Decimal, Decimal, Decimal, int | None]] = []
        seen: set[date] = set()
        for raw_row in values:
            row = _mapping(raw_row, TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)
            session = _session_date(row.get("datetime"))
            if session in seen:
                raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID)
            seen.add(session)
            open_price = _price(row.get("open"))
            high_price = _price(row.get("high"))
            low_price = _price(row.get("low"))
            close_price = _price(row.get("close"))
            raw_volume = _volume(row.get("volume"))
            volume = (
                raw_volume
                if request.adjustment_basis is DailyMarketBarAdjustmentBasis.RAW
                else None
            )
            if session <= cutoff.value:
                rows.append((session, open_price, high_price, low_price, close_price, volume))
        rows.sort(key=lambda item: item[0])
        rows = rows[-request.requested_session_count :]
        return tuple(self._bar(request, observed, row) for row in rows)

    @staticmethod
    def _bar(
        request: FetchCompletedDailyBarsRequest,
        observed_at: datetime,
        row: tuple[date, Decimal, Decimal, Decimal, Decimal, int | None],
    ) -> DailyMarketBarInput:
        session, open_price, high_price, low_price, close_price, volume = row
        mode = (
            "SPLITS"
            if request.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
            else "NONE"
        )
        mic_code = request.mic_code
        if mic_code is None:
            raise TwelveDataProviderError(TwelveDataErrorCategory.CONFIGURATION_INVALID)
        version = _source_version(
            request.symbol.value,
            mic_code,
            session,
            mode,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        )
        return DailyMarketBarInput(
            source_code=TWELVE_DATA_SOURCE_CODE,
            source_record_key=(
                f"{mic_code}.{request.symbol.value}.{session.strftime('%Y%m%d')}.{mode}"
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


def _validate_meta(meta: dict[str, Any], request: FetchCompletedDailyBarsRequest) -> None:
    required = {
        "symbol": request.symbol.value,
        "currency": "USD",
        "mic_code": request.mic_code,
        "interval": "1day",
        "exchange_timezone": _EXPECTED_TIMEZONE,
    }
    for name, expected in required.items():
        actual = meta.get(name)
        if not isinstance(actual, str) or actual.strip().upper() != str(expected).upper():
            raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)
    if not isinstance(meta.get("exchange"), str) or not meta["exchange"].strip():
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)


def _mapping(value: object, category: TwelveDataErrorCategory) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TwelveDataProviderError(category)
    return value


def _session_date(value: object) -> date:
    if not isinstance(value, str) or len(value.strip()) != 10:
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID)
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID) from None


def _price(value: object) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID)
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation:
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID) from None
    if not parsed.is_finite() or parsed <= 0:
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID)
    return parsed


def _volume(value: object) -> int | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not value.isdigit():
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID)
    parsed = int(value)
    if parsed < 0:
        raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_VALUE_INVALID)
    return parsed


def _source_version(
    symbol: str,
    mic_code: str,
    session: date,
    mode: str,
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
    volume: int | None,
) -> str:
    content = {
        "adjustment_mode": mode,
        "close": _decimal_text(close_price),
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
