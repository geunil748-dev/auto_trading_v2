from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from itertools import count
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDailyMarketBarIDFactory
from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse
from auto_trading_v2.adapters.market_data.alpaca import (
    AlpacaDailyMarketDataProvider,
    AlpacaRequestRateLimiter,
)
from auto_trading_v2.application.contracts.alpaca_ingestion import (
    AlpacaDailyMarketBarIngestionCommand,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import (
    AlpacaDailyMarketBarIngestionService,
    DailyMarketBarCreationService,
)
from auto_trading_v2.config import AlpacaMarketDataSettings
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import IdentifierFactory, SessionDate, Symbol

OBSERVED_AT = datetime(2026, 7, 15, 12, tzinfo=UTC)
CUTOFF = date(2026, 6, 30)
KEY_ID = "scripted-alpaca-key-id"
SECRET = "scripted-alpaca-secret"


class ScriptedTransport:
    def __init__(self, *responses: dict[str, object] | HttpResponse) -> None:
        self.responses = list(responses)
        self.calls: list[HttpRequest] = []

    def send(
        self,
        base_url: str,
        request: HttpRequest,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        assert base_url == "https://data.alpaca.markets"
        assert connect_timeout_seconds == 5
        assert read_timeout_seconds == 15
        self.calls.append(request)
        response = self.responses.pop(0)
        if isinstance(response, HttpResponse):
            return response
        return HttpResponse(200, (), json.dumps(response).encode())


def bars_payload(*, close_delta: float = 0.0, revised_index: int | None = None):
    bars: list[dict[str, object]] = []
    for index in range(21):
        session = date(2026, 6, 1) + timedelta(days=index)
        close = 100.0 + index + close_delta
        if index == revised_index:
            close += 0.5
        bars.append(
            {
                "t": f"{session.isoformat()}T04:00:00Z",
                "o": close - 0.5,
                "h": close + 2,
                "l": close - 2,
                "c": close,
                "v": 1000 + index,
                "n": 100 + index,
                "vw": close,
            }
        )
    return {"bars": bars, "symbol": "AAPL", "next_page_token": None}


def ingestion_command() -> AlpacaDailyMarketBarIngestionCommand:
    return AlpacaDailyMarketBarIngestionCommand(
        symbol=Symbol("AAPL"),
        mic_code="XNGS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=SessionDate(CUTOFF),
        requested_session_count=21,
    )


def ingestion_service(
    unit_of_work_factory: UnitOfWorkFactory,
    transport: ScriptedTransport,
    clock: FixedClock,
    identifier: int,
) -> AlpacaDailyMarketBarIngestionService:
    settings = AlpacaMarketDataSettings(
        enabled=True,
        base_url="https://data.alpaca.markets",
        api_key_id=SecretValue(KEY_ID),
        api_secret_key=SecretValue(SECRET),
        feed="iex",
        connect_timeout_seconds=5,
        read_timeout_seconds=15,
        requests_per_minute=200,
        maximum_retry_attempts=3,
        maximum_pages=5,
    )
    limiter = AlpacaRequestRateLimiter(
        10_000,
        monotonic=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )
    provider = AlpacaDailyMarketDataProvider(
        settings,
        transport,
        limiter,
        clock,
        sleeper=lambda _seconds: None,
    )
    identifiers = count(identifier)
    creation = DailyMarketBarCreationService(
        unit_of_work_factory,
        UuidDailyMarketBarIDFactory(IdentifierFactory(lambda: UUID(int=next(identifiers)))),
    )
    return AlpacaDailyMarketBarIngestionService(
        provider,
        unit_of_work_factory,
        creation,
        clock,
    )
