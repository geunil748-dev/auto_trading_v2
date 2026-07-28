from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    DailyMarketBarID,
    SessionDate,
    Symbol,
)

BASE_TIME = datetime(2026, 1, 1, 23, tzinfo=UTC)


def bar_input(
    index: int = 0,
    *,
    source_code: str = "UNIT_SOURCE",
    source_record_key: str | None = None,
    source_version: str = "v1",
    symbol: Symbol | None = None,
    adjustment_basis: DailyMarketBarAdjustmentBasis = (
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
    ),
    volume: int | None = 1000,
) -> DailyMarketBarInput:
    close = Decimal(100 + index)
    available_at = BASE_TIME + timedelta(days=index)
    return DailyMarketBarInput(
        source_code=source_code,
        source_record_key=source_record_key or f"bar-{index:03d}",
        source_version=source_version,
        symbol=Symbol("AAPL") if symbol is None else symbol,
        currency=Currency("USD"),
        adjustment_basis=adjustment_basis,
        session_date=SessionDate(date(2026, 1, 1) + timedelta(days=index)),
        observed_at=available_at - timedelta(hours=1),
        available_at=available_at,
        open_price=close - Decimal("0.5"),
        high_price=close + Decimal(2),
        low_price=close - Decimal(2),
        close_price=close,
        volume=None if volume is None else volume if volume == 0 else volume + index * 10,
    )


def stored_bar(index: int = 0, **changes: object) -> DailyMarketBar:
    source = bar_input(index)
    if changes:
        source = replace(source, **changes)
    new = NewDailyMarketBar(
        daily_market_bar_id=DailyMarketBarID(UUID(int=index + 1)),
        bar_key=daily_market_bar_key(source),
        content_digest=daily_market_bar_content_digest(source),
        bar_input=source,
    )
    return new.stored(source.available_at + timedelta(minutes=1))
