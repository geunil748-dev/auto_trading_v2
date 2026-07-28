from datetime import date

import pytest

from auto_trading_v2.adapters.market_data import HttpResponse
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_CAPABILITIES,
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from tests.unit.adapters.market_data.twelve_data.helpers import (
    API_KEY_SENTINEL,
    ScriptedTransport,
    fetch_request,
    payload,
    provider,
    response,
    settings,
)


def test_capabilities_are_explicit_and_adjusted_volume_is_unverified() -> None:
    assert TWELVE_DATA_CAPABILITIES.provider_code == TWELVE_DATA_SOURCE_CODE
    assert TWELVE_DATA_CAPABILITIES.official is True
    assert TWELVE_DATA_CAPABILITIES.requires_api_key is True
    assert TWELVE_DATA_CAPABILITIES.supports_raw_daily_bars is True
    assert TWELVE_DATA_CAPABILITIES.supports_split_adjusted_daily_bars is True
    assert TWELVE_DATA_CAPABILITIES.supports_adjusted_volume is False
    assert TWELVE_DATA_CAPABILITIES.maximum_rows_per_request == 5000


def test_exact_time_series_request_and_split_adjusted_mapping() -> None:
    transport = ScriptedTransport(response(payload()))
    subject = provider(transport)

    bars = subject.fetch_completed_daily_bars(fetch_request())

    assert len(bars) == 3
    assert all(bar.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED for bar in bars)
    assert all(bar.volume is None for bar in bars)
    base_url, request, connect_timeout, read_timeout = transport.calls[0]
    assert base_url == "https://api.twelvedata.com"
    assert request.method == "GET"
    assert request.path == "/time_series"
    assert dict(request.query) == {
        "symbol": "AAPL",
        "mic_code": "XNAS",
        "interval": "1day",
        "outputsize": "3",
        "end_date": "2026-07-01",
        "adjust": "splits",
        "order": "asc",
        "apikey": API_KEY_SENTINEL,
    }
    assert connect_timeout == 5
    assert read_timeout == 15
    assert API_KEY_SENTINEL not in repr(request)


def test_raw_mapping_preserves_valid_provider_volume() -> None:
    transport = ScriptedTransport(response(payload()))

    bars = provider(transport).fetch_completed_daily_bars(
        fetch_request(adjustment_basis=DailyMarketBarAdjustmentBasis.RAW)
    )

    assert [bar.volume for bar in bars] == [1000, 1000, 1000]
    assert dict(transport.calls[0][1].query)["adjust"] == "none"


@pytest.mark.parametrize("mic_code", ("XNAS", "XNYS", "XASE"))
def test_supported_mics_are_sent_explicitly(mic_code: str) -> None:
    transport = ScriptedTransport(response(payload(mic_code=mic_code)))

    provider(transport).fetch_completed_daily_bars(fetch_request(mic_code=mic_code))

    assert dict(transport.calls[0][1].query)["mic_code"] == mic_code


def test_unsupported_mic_is_rejected_before_network() -> None:
    transport = ScriptedTransport(response(payload()))

    with pytest.raises(TwelveDataProviderError) as raised:
        provider(transport).fetch_completed_daily_bars(fetch_request(mic_code="XLON"))

    assert raised.value.category is TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST
    assert transport.calls == []


@pytest.mark.parametrize(
    "first",
    (
        TimeoutError("sentinel must not escape"),
        OSError("sentinel must not escape"),
        HttpResponse(429, (), b""),
        HttpResponse(503, (), b""),
        response({"status": "error", "code": 429, "message": "sentinel"}),
    ),
)
def test_transient_failures_retry_with_bounded_backoff(first: object) -> None:
    transport = ScriptedTransport(first, response(payload()))  # type: ignore[arg-type]
    sleeps: list[float] = []

    bars = provider(transport, sleeps=sleeps).fetch_completed_daily_bars(fetch_request())

    assert len(bars) == 3
    assert len(transport.calls) == 2
    assert sleeps == [1.0]


def test_permanent_http_error_does_not_retry() -> None:
    transport = ScriptedTransport(HttpResponse(400, (), b"provider body sentinel"))

    with pytest.raises(TwelveDataProviderError) as raised:
        provider(transport).fetch_completed_daily_bars(fetch_request())

    assert raised.value.category is TwelveDataErrorCategory.HTTP_PERMANENT_FAILURE
    assert len(transport.calls) == 1
    assert "sentinel" not in str(raised.value)


def test_invalid_key_provider_error_does_not_retry_or_leak() -> None:
    transport = ScriptedTransport(
        response({"status": "error", "code": 401, "message": API_KEY_SENTINEL})
    )

    with pytest.raises(TwelveDataProviderError) as raised:
        provider(transport).fetch_completed_daily_bars(fetch_request())

    assert raised.value.category is TwelveDataErrorCategory.AUTHENTICATION_REJECTED
    assert len(transport.calls) == 1
    assert API_KEY_SENTINEL not in f"{raised.value!r}|{raised.value!s}"


def test_disabled_provider_has_no_network_call() -> None:
    transport = ScriptedTransport(response(payload()))

    with pytest.raises(TwelveDataProviderError) as raised:
        provider(
            transport,
            provider_settings=settings(enabled=False, api_key=None),
        ).fetch_completed_daily_bars(fetch_request(cutoff=date(2026, 7, 1)))

    assert raised.value.category is TwelveDataErrorCategory.PROVIDER_DISABLED
    assert transport.calls == []
