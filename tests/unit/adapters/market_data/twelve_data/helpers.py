from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse
from auto_trading_v2.adapters.market_data.twelve_data import TwelveDataCreditLimiter
from auto_trading_v2.adapters.market_data.twelve_data.provider import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataDailyMarketDataProvider,
)
from auto_trading_v2.application.ports.daily_market_data import (
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.config import TwelveDataMarketDataSettings
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import SessionDate, Symbol

NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)
API_KEY_SENTINEL = "twelve-data-secret-sentinel"


def settings(**changes: object) -> TwelveDataMarketDataSettings:
    values: dict[str, object] = {
        "enabled": True,
        "base_url": "https://api.twelvedata.com",
        "api_key": SecretValue(API_KEY_SENTINEL),
        "connect_timeout_seconds": 5.0,
        "read_timeout_seconds": 15.0,
        "credits_per_minute": 8,
        "daily_credit_budget": 800,
        "maximum_retry_attempts": 3,
        "maximum_requests_per_operation": 1,
    }
    values.update(changes)
    return TwelveDataMarketDataSettings(**values)  # type: ignore[arg-type]


def fetch_request(
    *,
    mic_code: str = "XNAS",
    adjustment_basis: DailyMarketBarAdjustmentBasis = (
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
    ),
    cutoff: date = date(2026, 7, 1),
    requested_session_count: int = 3,
) -> FetchCompletedDailyBarsRequest:
    return FetchCompletedDailyBarsRequest(
        source_code=TWELVE_DATA_SOURCE_CODE,
        symbol=Symbol("AAPL"),
        adjustment_basis=adjustment_basis,
        as_of=NOW,
        requested_session_count=requested_session_count,
        mic_code=mic_code,
        completed_through_session_date=SessionDate(cutoff),
    )


def payload(
    *,
    mic_code: str = "XNAS",
    symbol: str = "AAPL",
    currency: str = "USD",
    interval: str = "1day",
    values: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "meta": {
            "symbol": symbol,
            "currency": currency,
            "exchange": "NASDAQ",
            "mic_code": mic_code,
            "exchange_timezone": "America/New_York",
            "interval": interval,
        },
        "values": values
        if values is not None
        else [
            row("2026-06-29", "100"),
            row("2026-06-30", "101"),
            row("2026-07-01", "102"),
        ],
        "status": "ok",
    }


def row(session: str, close: str, *, volume: object = "1000") -> dict[str, object]:
    close_value = Decimal(close)
    return {
        "datetime": session,
        "open": format(close_value - 1, "f"),
        "high": format(close_value + 2, "f"),
        "low": format(close_value - 2, "f"),
        "close": close,
        "volume": volume,
    }


def response(body: object, status_code: int = 200) -> HttpResponse:
    return HttpResponse(status_code, (), json.dumps(body).encode())


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
    provider_settings: TwelveDataMarketDataSettings | None = None,
    clock: FixedClock | None = None,
    sleeps: list[float] | None = None,
) -> TwelveDataDailyMarketDataProvider:
    fixed_clock = clock or FixedClock(NOW)
    limiter = TwelveDataCreditLimiter(
        credits_per_minute=100,
        daily_credit_budget=100,
        clock=fixed_clock,
        monotonic=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )
    captured_sleeps = [] if sleeps is None else sleeps
    return TwelveDataDailyMarketDataProvider(
        provider_settings or settings(),
        transport,
        limiter,
        fixed_clock,
        sleeper=captured_sleeps.append,
    )
