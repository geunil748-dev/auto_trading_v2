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

SOURCE = "TWELVE_DATA_TIME_SERIES"
SYMBOL = Symbol("AAPL")
BASE_DATE = date(2026, 8, 3)
OBSERVATION_AS_OF = datetime(2026, 8, 15, tzinfo=UTC)


def outcome_bar(
    ordinal: int,
    *,
    close: str,
    high: str | None = None,
    low: str | None = None,
    source: str = SOURCE,
    symbol: Symbol = SYMBOL,
    basis: DailyMarketBarAdjustmentBasis = DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
    available_at: datetime | None = None,
    session_date: date | None = None,
    source_version: str | None = None,
) -> DailyMarketBar:
    close_value = Decimal(close)
    high_value = Decimal(high) if high is not None else close_value + Decimal("1")
    low_value = Decimal(low) if low is not None else close_value - Decimal("1")
    available = available_at or datetime(2026, 8, 4 + ordinal, 23, tzinfo=UTC)
    bar_input = DailyMarketBarInput(
        source,
        f"future-{ordinal}",
        source_version or f"v{ordinal}",
        symbol,
        Currency("USD"),
        basis,
        SessionDate(session_date or BASE_DATE + timedelta(days=ordinal)),
        available - timedelta(minutes=5),
        available,
        close_value,
        high_value,
        low_value,
        close_value,
        1_000,
    )
    candidate = NewDailyMarketBar(
        DailyMarketBarID(UUID(int=ordinal)),
        daily_market_bar_key(bar_input),
        daily_market_bar_content_digest(bar_input),
        bar_input,
    )
    return candidate.stored(available + timedelta(seconds=1))


def expected_sessions(bars: tuple[DailyMarketBar, ...]) -> tuple[SessionDate, ...]:
    return tuple(bar.bar_input.session_date for bar in bars)
