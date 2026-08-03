from datetime import timedelta

import pytest

from auto_trading_v2.domain.market_calendar import (
    CompletionGracePeriod,
    ExchangeCalendarFamily,
    MarketCalendarValidationError,
    calendar_family_for_mic,
    normalize_supported_mic,
)


@pytest.mark.parametrize(
    ("mic_code", "family"),
    (
        ("XNGS", ExchangeCalendarFamily.NASDAQ_CORE),
        ("XNGM", ExchangeCalendarFamily.NASDAQ_CORE),
        ("XNCM", ExchangeCalendarFamily.NASDAQ_CORE),
        ("XNYS", ExchangeCalendarFamily.NYSE_CORE),
        ("XASE", ExchangeCalendarFamily.NYSE_CORE),
    ),
)
def test_listing_mic_family_mapping_is_explicit(
    mic_code: str,
    family: ExchangeCalendarFamily,
) -> None:
    assert calendar_family_for_mic(mic_code) is family
    assert normalize_supported_mic(mic_code.lower()) == mic_code


@pytest.mark.parametrize("value", ("XNAS", "XLON", "", "ABC", None, 123))
def test_unsupported_or_malformed_mic_is_rejected(value: object) -> None:
    assert calendar_family_for_mic(value) is None
    with pytest.raises(MarketCalendarValidationError):
        normalize_supported_mic(value)


@pytest.mark.parametrize(
    "value",
    (timedelta(0), timedelta(minutes=15), timedelta(hours=24)),
)
def test_completion_grace_accepts_explicit_bounded_timedelta(value: timedelta) -> None:
    assert CompletionGracePeriod(value).value == value


@pytest.mark.parametrize(
    "value",
    (timedelta(microseconds=-1), timedelta(hours=24, microseconds=1), 0, 15.0, True),
)
def test_completion_grace_rejects_invalid_or_implicit_values(value: object) -> None:
    with pytest.raises(MarketCalendarValidationError):
        CompletionGracePeriod(value)  # type: ignore[arg-type]
