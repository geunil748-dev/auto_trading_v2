from dataclasses import replace
from datetime import date

import pytest

from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.application.services import DailyMarketBarCalendarValidator
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
    ProviderBarCalendarErrorCategory,
)
from auto_trading_v2.domain.primitives import SessionDate, Symbol
from tests.unit.domain.daily_market_bars.helpers import bar_input


def _observation(
    value: str,
    *,
    index: int,
    source_code: str = "UNIT_SOURCE",
    symbol: str = "AAPL",
):
    return replace(
        bar_input(1),
        source_code=source_code,
        source_record_key=f"calendar-{index}",
        symbol=Symbol(symbol),
        session_date=SessionDate.parse(value),
    )


def _validate(
    observations,
    *,
    mic_code: str = "XNGS",
    cutoff: str = "2026-07-06",
):
    return DailyMarketBarCalendarValidator(StaticOfficialUsEquityCalendar2026()).validate(
        mic_code=mic_code,
        calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
        calendar_version=ExchangeCalendarVersion.V2026_1,
        completed_through_session_date=SessionDate.parse(cutoff),
        observations=observations,
    )


def test_valid_sequence_is_preserved_in_chronological_order() -> None:
    values = (
        _observation("2026-06-29", index=1),
        _observation("2026-06-30", index=2),
        _observation("2026-07-01", index=3),
    )

    assert _validate(values) == values


@pytest.mark.parametrize(
    ("session_date", "category"),
    (
        ("2026-07-04", ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY),
        ("2026-07-03", ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY),
        ("2027-01-04", ProviderBarCalendarErrorCategory.OUT_OF_CALENDAR_COVERAGE),
    ),
)
def test_non_trading_or_out_of_range_bar_is_rejected(
    session_date: str,
    category: ProviderBarCalendarErrorCategory,
) -> None:
    with pytest.raises(MarketCalendarValidationError) as raised:
        _validate((_observation(session_date, index=1),), cutoff="2026-12-31")

    assert raised.value.category == category.value


def test_bar_after_completed_cutoff_is_rejected() -> None:
    with pytest.raises(MarketCalendarValidationError) as raised:
        _validate((_observation("2026-07-02", index=1),), cutoff="2026-07-01")

    assert raised.value.category == ProviderBarCalendarErrorCategory.AFTER_COMPLETED_CUTOFF


def test_duplicate_session_is_rejected() -> None:
    values = (
        _observation("2026-07-01", index=1),
        _observation("2026-07-01", index=2),
    )

    with pytest.raises(MarketCalendarValidationError) as raised:
        _validate(values)

    assert raised.value.category == ProviderBarCalendarErrorCategory.DUPLICATE_SESSION


@pytest.mark.parametrize(
    "values",
    (
        (
            _observation("2026-07-01", index=1),
            _observation("2026-06-30", index=2),
        ),
        (
            _observation("2026-06-30", index=1),
            _observation("2026-07-01", index=2, symbol="MSFT"),
        ),
        (
            _observation("2026-06-30", index=1),
            _observation("2026-07-01", index=2, source_code="OTHER_SOURCE"),
        ),
    ),
)
def test_inconsistent_or_unsorted_sequence_is_rejected(values) -> None:
    with pytest.raises(MarketCalendarValidationError) as raised:
        _validate(values)

    assert raised.value.category == ProviderBarCalendarErrorCategory.SEQUENCE_INCONSISTENT


def test_unsupported_mic_and_calendar_version_fail_closed() -> None:
    value = (_observation("2026-07-01", index=1),)
    validator = DailyMarketBarCalendarValidator(StaticOfficialUsEquityCalendar2026())

    with pytest.raises(MarketCalendarValidationError) as unsupported:
        _validate(value, mic_code="XNAS")
    with pytest.raises(MarketCalendarValidationError) as version:
        validator.validate(
            mic_code="XNGS",
            calendar_code=ExchangeCalendarCode.US_EQUITY_CORE,
            calendar_version="2027.v1",  # type: ignore[arg-type]
            completed_through_session_date=SessionDate(date(2026, 7, 1)),
            observations=value,
        )

    assert unsupported.value.category == ProviderBarCalendarErrorCategory.UNSUPPORTED_MIC
    assert version.value.category == ProviderBarCalendarErrorCategory.OUT_OF_CALENDAR_COVERAGE


def test_error_contains_only_safe_category_not_bar_payload() -> None:
    value = _observation("2026-07-03", index=1)

    with pytest.raises(MarketCalendarValidationError) as raised:
        _validate((value,))

    rendered = repr(raised.value)
    assert raised.value.category == ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY
    assert value.source_record_key not in rendered
    assert str(value.close_price) not in rendered
