from datetime import UTC, date, datetime

from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.repositories.daily_market_bars import (
    latest_available_daily_market_bars_for_sessions_statement,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import SessionDate, Symbol


def test_outcome_pit_statement_uses_exact_sessions_revision_rank_and_requested_order() -> None:
    sessions = (
        SessionDate(date(2026, 8, 4)),
        SessionDate(date(2026, 8, 6)),
        SessionDate(date(2026, 8, 7)),
    )
    statement = latest_available_daily_market_bars_for_sessions_statement(
        "TWELVE_DATA_TIME_SERIES",
        Symbol("AAPL"),
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        sessions,
        datetime(2026, 8, 8, tzinfo=UTC),
    )
    compiled = statement.compile(
        dialect=mssql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    sql = str(compiled)

    assert "row_number() OVER (PARTITION BY" in sql
    assert "available_at DESC" in sql
    assert "bar_key DESC" in sql
    assert "session_date IN" in sql
    assert "available_at <=" in sql
    assert "CASE" in sql and "ORDER BY" in sql
    assert "TWELVE_DATA_TIME_SERIES" in sql
    assert "SPLIT_ADJUSTED" in sql
    assert all(session.serialize() in sql for session in sessions)
