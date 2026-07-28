from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import count
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDailyMarketBarIDFactory
from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse
from auto_trading_v2.adapters.market_data.twelve_data import (
    TwelveDataCreditLimiter,
    TwelveDataDailyMarketDataProvider,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionCommand,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import (
    DailyMarketBarCreationService,
    TwelveDataDailyMarketBarIngestionService,
)
from auto_trading_v2.config import TwelveDataMarketDataSettings
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import IdentifierFactory, SessionDate, Symbol

OBSERVED_AT = datetime(2026, 7, 15, 12, tzinfo=UTC)
CUTOFF = date(2026, 6, 30)
API_KEY = "scripted-contract-key"


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
        assert base_url == "https://api.twelvedata.com"
        assert connect_timeout_seconds == 5
        assert read_timeout_seconds == 15
        self.calls.append(request)
        response = self.responses.pop(0)
        if isinstance(response, HttpResponse):
            return response
        return HttpResponse(200, (), json.dumps(response).encode())


def time_series_payload(*, revised_index: int | None = None) -> dict[str, object]:
    values: list[dict[str, object]] = []
    for index in range(21):
        session = date(2026, 6, 1) + timedelta(days=index)
        close = Decimal(100 + index)
        if index == revised_index:
            close += Decimal("0.5")
        values.append(
            {
                "datetime": session.isoformat(),
                "open": format(close - Decimal("0.5"), "f"),
                "high": format(close + Decimal(2), "f"),
                "low": format(close - Decimal(2), "f"),
                "close": format(close, "f"),
                "volume": str(1000 + index),
            }
        )
    return {
        "meta": {
            "symbol": "AAPL",
            "currency": "USD",
            "exchange": "NASDAQ",
            "mic_code": "XNGS",
            "exchange_timezone": "America/New_York",
            "interval": "1day",
        },
        "values": values,
        "status": "ok",
    }


def ingestion_command() -> TwelveDataDailyMarketBarIngestionCommand:
    return TwelveDataDailyMarketBarIngestionCommand(
        symbol=Symbol("AAPL"),
        mic_code="XNGS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=SessionDate(CUTOFF),
        requested_session_count=21,
    )


def provider(
    transport: ScriptedTransport,
    clock: FixedClock,
) -> TwelveDataDailyMarketDataProvider:
    settings = TwelveDataMarketDataSettings(
        enabled=True,
        base_url="https://api.twelvedata.com",
        api_key=SecretValue(API_KEY),
        connect_timeout_seconds=5,
        read_timeout_seconds=15,
        credits_per_minute=100,
        daily_credit_budget=100,
        maximum_retry_attempts=3,
        maximum_requests_per_operation=1,
    )
    limiter = TwelveDataCreditLimiter(
        credits_per_minute=100,
        daily_credit_budget=100,
        clock=clock,
        monotonic=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )
    return TwelveDataDailyMarketDataProvider(
        settings,
        transport,
        limiter,
        clock,
        sleeper=lambda _seconds: None,
    )


def ingestion_service(
    unit_of_work_factory: UnitOfWorkFactory,
    transport: ScriptedTransport,
    clock: FixedClock,
    identifier: int,
) -> TwelveDataDailyMarketBarIngestionService:
    identifiers = count(identifier)
    creation = DailyMarketBarCreationService(
        unit_of_work_factory,
        UuidDailyMarketBarIDFactory(IdentifierFactory(lambda: UUID(int=next(identifiers)))),
    )
    return TwelveDataDailyMarketBarIngestionService(
        provider(transport, clock),
        unit_of_work_factory,
        creation,
        clock,
    )
