"""Safe row mapping for canonical DailyMarketBar records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    Currency,
    DailyMarketBarID,
    SessionDate,
    Symbol,
)


def map_daily_market_bar(row: Mapping[Any, Any]) -> DailyMarketBar:
    """Map canonical columns without retaining rejected provider values in errors."""

    try:
        bar_input = DailyMarketBarInput(
            source_code=str(row["source_code"]),
            source_record_key=str(row["source_record_key"]),
            source_version=str(row["source_version"]),
            symbol=Symbol(str(row["symbol"])),
            currency=Currency(str(row["currency"])),
            adjustment_basis=DailyMarketBarAdjustmentBasis(str(row["adjustment_basis"])),
            session_date=SessionDate(_date(row["session_date"])),
            observed_at=_datetime(row["observed_at"]),
            available_at=_datetime(row["available_at"]),
            open_price=_decimal(row["open_price"]),
            high_price=_decimal(row["high_price"]),
            low_price=_decimal(row["low_price"]),
            close_price=_decimal(row["close_price"]),
            volume=_volume(row["volume"]),
        )
        return DailyMarketBar(
            daily_market_bar_id=DailyMarketBarID(_uuid(row["daily_market_bar_id"])),
            bar_key=str(row["bar_key"]),
            content_digest=str(row["content_digest"]),
            bar_input=bar_input,
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("daily_market_bar") from None


def new_daily_market_bar_values(bar: NewDailyMarketBar) -> dict[str, object]:
    source = bar.bar_input
    return {
        "daily_market_bar_id": bar.daily_market_bar_id.value,
        "bar_key": bar.bar_key,
        "content_digest": bar.content_digest,
        "source_code": source.source_code,
        "source_record_key": source.source_record_key,
        "source_version": source.source_version,
        "symbol": source.symbol.value,
        "currency": source.currency.code,
        "adjustment_basis": source.adjustment_basis.value,
        "session_date": source.session_date.value,
        "observed_at": source.observed_at,
        "available_at": source.available_at,
        "open_price": source.open_price,
        "high_price": source.high_price,
        "low_price": source.low_price,
        "close_price": source.close_price,
        "volume": source.volume,
    }


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _date(value: object) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError
    return value


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def _volume(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
