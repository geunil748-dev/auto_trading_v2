from datetime import UTC, date, datetime, timedelta

from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.application.services.daily_feature_outcome_builder import future_sessions
from auto_trading_v2.domain.primitives import SessionDate


def _future(source: date, horizon: int = 1) -> tuple[object, ...]:
    sessions = StaticOfficialUsEquityCalendar2026().sessions("XNGS")
    selected = future_sessions(sessions, SessionDate(source), horizon)
    assert selected is not None
    return selected


def test_future_sessions_skip_independence_holiday_and_weekend() -> None:
    selected = _future(date(2026, 7, 2), 2)

    assert [session.session_date.value for session in selected] == [
        date(2026, 7, 6),
        date(2026, 7, 7),
    ]


def test_horizon_crosses_thanksgiving_and_uses_early_close() -> None:
    selected = _future(date(2026, 11, 25), 1)

    assert selected[0].session_date.value == date(2026, 11, 27)
    assert selected[0].close_at == datetime(2026, 11, 27, 18, tzinfo=UTC)


def test_maturity_equality_with_zero_and_fifteen_minute_grace() -> None:
    terminal = _future(date(2026, 8, 3), 1)[0]

    zero_eligible = terminal.close_at
    fifteen_eligible = terminal.close_at + timedelta(minutes=15)

    assert zero_eligible <= terminal.close_at
    assert terminal.close_at + timedelta(minutes=14, seconds=59) < fifteen_eligible
    assert terminal.close_at + timedelta(minutes=15) >= fifteen_eligible


def test_calendar_out_of_coverage_does_not_invent_2027_session() -> None:
    assert _future(date(2026, 12, 31), 1) == ()
