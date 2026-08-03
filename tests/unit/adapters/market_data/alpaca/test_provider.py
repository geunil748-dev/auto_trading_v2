from datetime import date

import pytest

from auto_trading_v2.adapters.market_data import HttpResponse
from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_CAPABILITIES,
    ALPACA_SOURCE_CODE,
    AlpacaErrorCategory,
    AlpacaProviderError,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from tests.unit.adapters.market_data.alpaca.helpers import (
    KEY_ID,
    SECRET,
    ScriptedTransport,
    bar,
    fetch_request,
    payload,
    provider,
    response,
    settings,
)


def test_capabilities_declare_validation_provider_contract() -> None:
    assert ALPACA_CAPABILITIES.provider_code == ALPACA_SOURCE_CODE
    assert ALPACA_CAPABILITIES.official is True
    assert ALPACA_CAPABILITIES.requires_api_key is True
    assert ALPACA_CAPABILITIES.supports_raw_daily_bars is True
    assert ALPACA_CAPABILITIES.supports_split_adjusted_daily_bars is True
    assert ALPACA_CAPABILITIES.supports_adjusted_volume is True
    assert ALPACA_CAPABILITIES.supports_completed_cutoff is True
    assert ALPACA_CAPABILITIES.supports_pagination is True
    assert ALPACA_CAPABILITIES.maximum_rows_per_request == 10_000


def test_exact_single_symbol_iex_request_is_header_authenticated_and_safe() -> None:
    transport = ScriptedTransport(response(payload()))

    bars = provider(transport).fetch_completed_daily_bars(fetch_request())

    assert len(bars) == 3
    base_url, request, connect_timeout, read_timeout = transport.calls[0]
    assert base_url == "https://data.alpaca.markets"
    assert request.method == "GET"
    assert request.path == "/v2/stocks/AAPL/bars"
    assert dict(request.query) == {
        "timeframe": "1Day",
        "feed": "iex",
        "adjustment": "split",
        "currency": "USD",
        "sort": "asc",
        "start": "2026-06-02T00:00:00Z",
        "end": "2026-07-18T00:00:00Z",
        "limit": "23",
        "asof": "2026-07-17",
    }
    assert "mic_code" not in dict(request.query)
    assert "apikey" not in dict(request.query)
    assert request.headers == (
        ("APCA-API-KEY-ID", KEY_ID),
        ("APCA-API-SECRET-KEY", SECRET),
    )
    rendered = f"{request!r}|{request!s}"
    assert KEY_ID not in rendered
    assert SECRET not in rendered
    assert "APCA-API" not in rendered
    assert connect_timeout == 5
    assert read_timeout == 15


def test_raw_path_is_explicit_and_preserves_volume() -> None:
    transport = ScriptedTransport(response(payload()))

    bars = provider(transport).fetch_completed_daily_bars(
        fetch_request(adjustment_basis=DailyMarketBarAdjustmentBasis.RAW)
    )

    assert dict(transport.calls[0][1].query)["adjustment"] == "raw"
    assert all(bar.adjustment_basis is DailyMarketBarAdjustmentBasis.RAW for bar in bars)
    assert [bar.volume for bar in bars] == [1000, 1000, 1000]


@pytest.mark.parametrize("mic_code", ("XNGS", "XNGM", "XNCM", "XNYS", "XASE"))
def test_supported_listing_mics_remain_identity_only(mic_code: str) -> None:
    transport = ScriptedTransport(response(payload()))

    bars = provider(transport).fetch_completed_daily_bars(fetch_request(mic_code=mic_code))

    assert bars[0].source_record_key.startswith(f"{mic_code}.AAPL.")
    assert "mic_code" not in dict(transport.calls[0][1].query)


@pytest.mark.parametrize("mic_code", ("XNAS", "XLON"))
def test_unsupported_mic_is_rejected_without_alias_or_network(mic_code: str) -> None:
    transport = ScriptedTransport(response(payload()))

    with pytest.raises(AlpacaProviderError) as raised:
        provider(transport).fetch_completed_daily_bars(fetch_request(mic_code=mic_code))

    assert raised.value.category is AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST
    assert transport.calls == []


def test_pagination_uses_token_without_exposing_it_and_returns_latest_sessions() -> None:
    token = "opaque-pagination-token-sentinel"
    first = payload(
        [
            bar("2026-07-14T04:00:00Z", 99.5),
            bar("2026-07-15T04:00:00Z", 100.5),
        ],
        next_page_token=token,
    )
    second = payload(
        [
            bar("2026-07-16T04:00:00Z", 101.5),
            bar("2026-07-17T04:00:00Z", 102.5),
        ]
    )
    transport = ScriptedTransport(response(first), response(second))

    bars = provider(transport).fetch_completed_daily_bars(fetch_request(requested_session_count=3))

    assert [bar.session_date.serialize() for bar in bars] == [
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
    ]
    assert dict(transport.calls[1][1].query)["page_token"] == token
    assert token not in repr(transport.calls[1][1])


def test_repeated_page_token_and_maximum_page_exhaustion_are_rejected() -> None:
    repeated = ScriptedTransport(
        response(payload(next_page_token="repeat")),
        response(payload([], next_page_token="repeat")),
    )
    with pytest.raises(AlpacaProviderError) as raised:
        provider(repeated).fetch_completed_daily_bars(fetch_request())
    assert raised.value.category is AlpacaErrorCategory.PAGINATION_INVALID

    limited = ScriptedTransport(response(payload(next_page_token="more")))
    with pytest.raises(AlpacaProviderError) as limited_error:
        provider(
            limited,
            provider_settings=settings(maximum_pages=1),
        ).fetch_completed_daily_bars(fetch_request())
    assert limited_error.value.category is AlpacaErrorCategory.PAGINATION_INVALID


@pytest.mark.parametrize(
    "first",
    (
        TimeoutError("raw timeout sentinel"),
        OSError("raw connection sentinel"),
        HttpResponse(429, (), b""),
        HttpResponse(500, (), b""),
        HttpResponse(502, (), b""),
        HttpResponse(503, (), b""),
        HttpResponse(504, (), b""),
    ),
)
def test_only_documented_transient_failures_retry(first: Exception | HttpResponse) -> None:
    transport = ScriptedTransport(first, response(payload()))
    sleeps: list[float] = []

    bars = provider(transport, sleeps=sleeps).fetch_completed_daily_bars(fetch_request())

    assert len(bars) == 3
    assert len(transport.calls) == 2
    assert sleeps == [1.0]


@pytest.mark.parametrize(
    ("status", "category"),
    (
        (400, AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST),
        (401, AlpacaErrorCategory.AUTHENTICATION_REJECTED),
        (403, AlpacaErrorCategory.ACCESS_FORBIDDEN),
        (404, AlpacaErrorCategory.INSTRUMENT_NOT_FOUND),
        (422, AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST),
        (418, AlpacaErrorCategory.HTTP_PERMANENT_FAILURE),
    ),
)
def test_permanent_errors_are_distinct_safe_and_not_retried(
    status: int,
    category: AlpacaErrorCategory,
) -> None:
    transport = ScriptedTransport(
        response(
            {
                "code": 42210000,
                "message": f"invalid timeframe {SECRET}",
            },
            status,
        )
    )

    with pytest.raises(AlpacaProviderError) as raised:
        provider(transport).fetch_completed_daily_bars(fetch_request())

    assert raised.value.category is category
    assert raised.value.http_status == status
    assert raised.value.provider_code == 42210000
    assert raised.value.safe_parameter_hint == "timeframe"
    assert len(transport.calls) == 1
    assert SECRET not in f"{raised.value!r}|{raised.value!s}"


def test_disabled_or_over_limit_request_never_reaches_network() -> None:
    disabled_transport = ScriptedTransport(response(payload()))
    with pytest.raises(AlpacaProviderError) as disabled:
        provider(
            disabled_transport,
            provider_settings=settings(
                enabled=False,
                api_key_id=None,
                api_secret_key=None,
            ),
        ).fetch_completed_daily_bars(fetch_request())
    assert disabled.value.category is AlpacaErrorCategory.PROVIDER_DISABLED
    assert disabled_transport.calls == []

    over_limit = ScriptedTransport(response(payload()))
    with pytest.raises(AlpacaProviderError):
        provider(over_limit).fetch_completed_daily_bars(
            fetch_request(requested_session_count=10_001, cutoff=date(2026, 7, 17))
        )
    assert over_limit.calls == []
