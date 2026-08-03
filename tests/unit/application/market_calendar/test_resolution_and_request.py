from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationOutcome,
)
from auto_trading_v2.application.services import (
    CompletedDailyBarsRequestFactory,
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.market_calendar import (
    CompletedSessionResolutionOutcome,
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
)
from auto_trading_v2.domain.primitives import Symbol

_ET = ZoneInfo("America/New_York")


@pytest.fixture
def resolver() -> UsEquityCompletedSessionResolver:
    return UsEquityCompletedSessionResolver(StaticOfficialUsEquityCalendar2026())


def _et(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0):
    return datetime(year, month, day, hour, minute, second, tzinfo=_ET)


def _resolve(
    resolver: UsEquityCompletedSessionResolver,
    as_of: datetime,
    grace: timedelta = timedelta(0),
):
    return resolver.resolve(
        mic_code="XNGS",
        as_of=as_of,
        completion_grace=CompletionGracePeriod(grace),
    )


def test_first_session_is_not_completed_before_close(
    resolver: UsEquityCompletedSessionResolver,
) -> None:
    result = _resolve(resolver, _et(2026, 1, 2, 15, 59, 59))

    assert result.outcome is CompletedSessionResolutionOutcome.NO_COMPLETED_SESSION
    assert result.session is None


def test_exact_regular_close_is_completed_with_zero_grace(
    resolver: UsEquityCompletedSessionResolver,
) -> None:
    result = _resolve(resolver, _et(2026, 1, 2, 16))

    assert result.outcome is CompletedSessionResolutionOutcome.RESOLVED
    assert result.session is not None
    assert result.session.session_date.value == date(2026, 1, 2)
    assert result.previous_session_date is None
    assert result.eligible_at == result.session.close_at


@pytest.mark.parametrize(
    "as_of", (_et(2026, 7, 3, 12), _et(2026, 7, 4, 12), _et(2026, 7, 5, 12), _et(2026, 7, 6, 9))
)
def test_holiday_weekend_and_next_preopen_resolve_previous_session(
    resolver: UsEquityCompletedSessionResolver,
    as_of: datetime,
) -> None:
    result = _resolve(resolver, as_of)

    assert result.outcome is CompletedSessionResolutionOutcome.RESOLVED
    assert result.session is not None
    assert result.session.session_date.value == date(2026, 7, 2)


def test_next_regular_session_resolves_after_close_and_grace(
    resolver: UsEquityCompletedSessionResolver,
) -> None:
    result = _resolve(resolver, _et(2026, 7, 6, 16, 15), timedelta(minutes=15))

    assert result.session is not None
    assert result.session.session_date.value == date(2026, 7, 6)


@pytest.mark.parametrize("session_date", ((2026, 11, 27), (2026, 12, 24)))
def test_early_close_completion_and_fifteen_minute_grace(
    resolver: UsEquityCompletedSessionResolver,
    session_date: tuple[int, int, int],
) -> None:
    year, month, day = session_date
    before = _resolve(resolver, _et(year, month, day, 12, 59, 59))
    exact = _resolve(resolver, _et(year, month, day, 13))
    grace_before = _resolve(
        resolver,
        _et(year, month, day, 13, 14, 59),
        timedelta(minutes=15),
    )
    grace_exact = _resolve(
        resolver,
        _et(year, month, day, 13, 15),
        timedelta(minutes=15),
    )

    expected = date(year, month, day)
    assert before.session is not None and before.session.session_date.value != expected
    assert exact.session is not None and exact.session.session_date.value == expected
    assert grace_before.session is not None
    assert grace_before.session.session_date.value != expected
    assert grace_exact.session is not None
    assert grace_exact.session.session_date.value == expected


def test_last_session_and_out_of_coverage_are_fail_closed(
    resolver: UsEquityCompletedSessionResolver,
) -> None:
    before = _resolve(resolver, _et(2026, 12, 31, 15, 59, 59))
    exact = _resolve(resolver, _et(2026, 12, 31, 16))
    outside = _resolve(resolver, _et(2027, 1, 1, 12))
    prior = _resolve(resolver, _et(2025, 12, 31, 12))

    assert before.session is not None
    assert before.session.session_date.value == date(2026, 12, 30)
    assert exact.session is not None
    assert exact.session.session_date.value == date(2026, 12, 31)
    assert outside.outcome is CompletedSessionResolutionOutcome.CALENDAR_OUT_OF_COVERAGE
    assert outside.session is None
    assert prior.outcome is CompletedSessionResolutionOutcome.CALENDAR_OUT_OF_COVERAGE


def test_unsupported_mic_and_naive_as_of_do_not_resolve(
    resolver: UsEquityCompletedSessionResolver,
) -> None:
    unsupported = resolver.resolve(
        mic_code="XNAS",
        as_of=_et(2026, 7, 6, 17),
        completion_grace=CompletionGracePeriod(timedelta(0)),
    )

    assert unsupported.outcome is CompletedSessionResolutionOutcome.UNSUPPORTED_MIC
    with pytest.raises(MarketCalendarValidationError):
        resolver.resolve(
            mic_code="XNGS",
            as_of=datetime(2026, 7, 6, 17),
            completion_grace=CompletionGracePeriod(timedelta(0)),
        )


def test_request_factory_creates_exact_cutoff_and_calendar_metadata(
    resolver: UsEquityCompletedSessionResolver,
) -> None:
    result = CompletedDailyBarsRequestFactory(resolver).create(
        source_code="TWELVE_DATA_TIME_SERIES",
        symbol=Symbol("AAPL"),
        mic_code="XNGS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        as_of=_et(2026, 7, 6, 16, 15),
        requested_session_count=30,
        completion_grace=CompletionGracePeriod(timedelta(minutes=15)),
    )

    assert result.outcome is CompletedDailyBarsRequestCreationOutcome.CREATED
    assert result.calendar_code is ExchangeCalendarCode.US_EQUITY_CORE
    assert result.calendar_version is ExchangeCalendarVersion.V2026_1
    assert result.request is not None
    assert result.request.completed_through_session_date is not None
    assert result.request.completed_through_session_date.value == date(2026, 7, 6)
    assert result.request.as_of == _et(2026, 7, 6, 16, 15).astimezone(result.request.as_of.tzinfo)
    assert result.eligible_at is not None


@pytest.mark.parametrize(
    ("mic_code", "as_of", "outcome"),
    (
        ("XNAS", _et(2026, 7, 6, 17), CompletedDailyBarsRequestCreationOutcome.UNSUPPORTED_MIC),
        (
            "XNGS",
            _et(2027, 1, 1, 12),
            CompletedDailyBarsRequestCreationOutcome.CALENDAR_OUT_OF_COVERAGE,
        ),
        (
            "XNGS",
            _et(2026, 1, 2, 15),
            CompletedDailyBarsRequestCreationOutcome.NO_COMPLETED_SESSION,
        ),
    ),
)
def test_request_factory_failure_creates_no_placeholder_request(
    resolver: UsEquityCompletedSessionResolver,
    mic_code: str,
    as_of: datetime,
    outcome: CompletedDailyBarsRequestCreationOutcome,
) -> None:
    result = CompletedDailyBarsRequestFactory(resolver).create(
        source_code="ALPACA_IEX_STOCK_BARS",
        symbol=Symbol("AAPL"),
        mic_code=mic_code,
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        as_of=as_of,
        requested_session_count=30,
        completion_grace=CompletionGracePeriod(timedelta(0)),
    )

    assert result.outcome is outcome
    assert result.request is None
    assert result.completed_session is None
    assert result.eligible_at is None
    assert result.safe_reason_code == outcome.value
