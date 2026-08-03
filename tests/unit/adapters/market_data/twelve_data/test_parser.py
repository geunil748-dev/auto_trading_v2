from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.adapters.market_data.twelve_data import (
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.adapters.market_data.twelve_data.parser import (
    TwelveDataTimeSeriesParser,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from tests.unit.adapters.market_data.twelve_data.helpers import (
    NOW,
    fetch_request,
    payload,
    row,
)


def parse(body: object, **request_changes: object):
    request = fetch_request(**request_changes)  # type: ignore[arg-type]
    return TwelveDataTimeSeriesParser().parse(body, request, NOW)


@pytest.mark.parametrize(
    ("meta_key", "value"),
    (
        ("symbol", "MSFT"),
        ("currency", "EUR"),
        ("mic_code", "XNYS"),
        ("interval", "1h"),
        ("exchange_timezone", "UTC"),
        ("exchange", ""),
    ),
)
def test_meta_mismatch_is_rejected(meta_key: str, value: str) -> None:
    body = payload()
    body["meta"][meta_key] = value  # type: ignore[index]

    with pytest.raises(TwelveDataProviderError) as raised:
        parse(body)

    assert raised.value.category is TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID


@pytest.mark.parametrize("value", ("", "nan", "Infinity", "-1", "not-a-number"))
def test_invalid_price_strings_are_rejected(value: str) -> None:
    body = payload(values=[row("2026-07-01", "100")])
    body["values"][0]["open"] = value  # type: ignore[index]

    with pytest.raises(TwelveDataProviderError) as raised:
        parse(body)

    assert raised.value.category is TwelveDataErrorCategory.RESPONSE_VALUE_INVALID


def test_float_price_is_never_coerced() -> None:
    body = payload(values=[row("2026-07-01", "100")])
    body["values"][0]["close"] = 100.5  # type: ignore[index]

    with pytest.raises(TwelveDataProviderError):
        parse(body)


@pytest.mark.parametrize("session", ("20260701", "2026-02-30", "not-a-date"))
def test_malformed_date_is_rejected(session: str) -> None:
    with pytest.raises(TwelveDataProviderError):
        parse(payload(values=[row(session, "100")]))


@pytest.mark.parametrize("volume", ("-1", True, "1.5"))
def test_invalid_volume_is_rejected_even_when_adjusted(volume: object) -> None:
    with pytest.raises(TwelveDataProviderError):
        parse(payload(values=[row("2026-07-01", "100", volume=volume)]))


def test_duplicate_session_is_rejected() -> None:
    with pytest.raises(TwelveDataProviderError):
        parse(
            payload(
                values=[
                    row("2026-07-01", "100"),
                    row("2026-07-01", "101"),
                ]
            )
        )


def test_cutoff_filter_sort_and_requested_count_trim() -> None:
    body = payload(
        values=[
            row("2026-07-02", "103"),
            row("2026-06-29", "100"),
            row("2026-07-01", "102"),
            row("2026-06-30", "101"),
        ]
    )

    bars = parse(body, requested_session_count=2)

    assert [bar.session_date.serialize() for bar in bars] == ["2026-06-30", "2026-07-01"]


def test_fetch_time_does_not_change_source_version() -> None:
    parser = TwelveDataTimeSeriesParser()
    request = fetch_request(requested_session_count=1)
    body = payload(values=[row("2026-07-01", "100")])

    first = parser.parse(body, request, NOW)[0]
    second = parser.parse(body, request, NOW + timedelta(hours=1))[0]

    assert first.source_record_key == "XNGS.AAPL.20260701.SPLITS"
    assert first.source_version == second.source_version
    assert first.source_record_key == second.source_record_key
    assert first.available_at != second.available_at


def test_provider_content_change_creates_new_source_version() -> None:
    parser = TwelveDataTimeSeriesParser()
    request = fetch_request(requested_session_count=1)
    first_body = payload(values=[row("2026-07-01", "100")])
    revised_body = deepcopy(first_body)
    revised_body["values"][0]["close"] = "101"  # type: ignore[index]
    revised_body["values"][0]["high"] = "103"  # type: ignore[index]

    first = parser.parse(first_body, request, NOW)[0]
    revised = parser.parse(revised_body, request, NOW)[0]

    assert first.source_version != revised.source_version
    assert first.source_record_key == revised.source_record_key


def test_raw_volume_is_integer_and_adjusted_volume_is_none() -> None:
    body = payload(values=[row("2026-07-01", "100", volume="1234")])

    raw = parse(body, adjustment_basis=DailyMarketBarAdjustmentBasis.RAW)[0]
    adjusted = parse(body)[0]

    assert raw.volume == 1234
    assert adjusted.volume is None
    assert adjusted.close_price == Decimal("100")
