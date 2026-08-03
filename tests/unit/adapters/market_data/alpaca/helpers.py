from __future__ import annotations

import json
from datetime import UTC, date, datetime

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse
from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_SOURCE_CODE,
    AlpacaDailyMarketDataProvider,
    AlpacaRequestRateLimiter,
)
from auto_trading_v2.application.ports.daily_market_data import (
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.config import AlpacaMarketDataSettings
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import SessionDate, Symbol

NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)
KEY_ID = "alpaca-key-id-sentinel"
SECRET = "alpaca-secret-sentinel"


def settings(**changes: object) -> AlpacaMarketDataSettings:
    values: dict[str, object] = {
        "enabled": True,
        "base_url": "https://data.alpaca.markets",
        "api_key_id": SecretValue(KEY_ID),
        "api_secret_key": SecretValue(SECRET),
        "feed": "iex",
        "connect_timeout_seconds": 5.0,
        "read_timeout_seconds": 15.0,
        "requests_per_minute": 200,
        "maximum_retry_attempts": 3,
        "maximum_pages": 5,
    }
    values.update(changes)
    return AlpacaMarketDataSettings(**values)  # type: ignore[arg-type]


def fetch_request(
    *,
    mic_code: str = "XNGS",
    adjustment_basis: DailyMarketBarAdjustmentBasis = (
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
    ),
    cutoff: date = date(2026, 7, 17),
    requested_session_count: int = 3,
) -> FetchCompletedDailyBarsRequest:
    return FetchCompletedDailyBarsRequest(
        source_code=ALPACA_SOURCE_CODE,
        symbol=Symbol("AAPL"),
        adjustment_basis=adjustment_basis,
        as_of=NOW,
        requested_session_count=requested_session_count,
        mic_code=mic_code,
        completed_through_session_date=SessionDate(cutoff),
    )


def bar(timestamp: str, close: float, *, volume: object = 1000) -> dict[str, object]:
    return {
        "t": timestamp,
        "o": close - 1,
        "h": close + 2,
        "l": close - 2,
        "c": close,
        "v": volume,
        "n": 100,
        "vw": close,
    }


def payload(
    bars: list[dict[str, object]] | None = None,
    *,
    symbol: str = "AAPL",
    next_page_token: object = None,
) -> dict[str, object]:
    return {
        "bars": bars
        if bars is not None
        else [
            bar("2026-07-15T04:00:00Z", 100.5),
            bar("2026-07-16T04:00:00Z", 101.5),
            bar("2026-07-17T04:00:00Z", 102.5),
        ],
        "symbol": symbol,
        "next_page_token": next_page_token,
    }


def response(body: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status, (), json.dumps(body).encode())


class ScriptedTransport:
    def __init__(self, *outcomes: HttpResponse | Exception) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, HttpRequest, float, float]] = []

    def send(
        self,
        base_url: str,
        request: HttpRequest,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append((base_url, request, connect_timeout_seconds, read_timeout_seconds))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def provider(
    transport: ScriptedTransport,
    *,
    provider_settings: AlpacaMarketDataSettings | None = None,
    sleeps: list[float] | None = None,
) -> AlpacaDailyMarketDataProvider:
    limiter = AlpacaRequestRateLimiter(
        10_000,
        monotonic=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )
    captured = [] if sleeps is None else sleeps
    return AlpacaDailyMarketDataProvider(
        provider_settings or settings(),
        transport,
        limiter,
        FixedClock(NOW),
        sleeper=captured.append,
    )
