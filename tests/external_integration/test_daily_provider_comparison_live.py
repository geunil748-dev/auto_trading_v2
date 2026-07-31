from datetime import timedelta
from itertools import count
from uuid import UUID

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import SystemClock
from auto_trading_v2.adapters.identifiers import UuidDailyMarketBarIDFactory
from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse, UrllibHttpTransport
from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_SOURCE_CODE,
    AlpacaDailyMarketDataProvider,
    AlpacaRequestRateLimiter,
)
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataCreditLimiter,
    TwelveDataDailyMarketDataProvider,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    feature_snapshots,
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.alpaca_ingestion import (
    AlpacaDailyMarketBarIngestionCommand,
    AlpacaIngestionOutcome,
)
from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationOutcome,
)
from auto_trading_v2.application.contracts.daily_bar_comparison import (
    CompareDailyBarProvidersCommand,
    DailyBarProviderComparisonOutcome,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionCommand,
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.services import (
    AlpacaDailyMarketBarIngestionService,
    CompletedDailyBarsRequestFactory,
    DailyBarProviderComparisonService,
    DailyMarketBarCalendarValidator,
    DailyMarketBarCreationService,
    TwelveDataDailyMarketBarIngestionService,
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.config import (
    load_alpaca_market_data_settings,
    load_twelve_data_market_data_settings,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import IdentifierFactory, Symbol
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.external_integration
_ALPACA = load_alpaca_market_data_settings()
_TWELVE = load_twelve_data_market_data_settings()
if (
    not _ALPACA.enabled
    or _ALPACA.api_key_id is None
    or _ALPACA.api_secret_key is None
    or not _TWELVE.enabled
    or _TWELVE.api_key is None
):
    pytestmark = [
        pytest.mark.external_integration,
        pytest.mark.skip(reason="Both provider credentials are required for live comparison"),
    ]
_SIDE_EFFECT_TABLES = (feature_snapshots, recommendations, trade_intents, paper_orders)


class CountingTransport:
    def __init__(self) -> None:
        self.calls: list[HttpRequest] = []
        self._delegate = UrllibHttpTransport()

    def send(
        self,
        base_url: str,
        request: HttpRequest,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append(request)
        return self._delegate.send(
            base_url,
            request,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )


def test_live_one_request_per_provider_produces_read_only_comparison(
    mssql_database: TemporaryMssqlDatabase,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    with mssql_database.engine.connect() as connection:
        before = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in _SIDE_EFFECT_TABLES
        )
    clock = SystemClock()
    calendar = StaticOfficialUsEquityCalendar2026()
    request_factory = CompletedDailyBarsRequestFactory(UsEquityCompletedSessionResolver(calendar))
    alpaca_transport = CountingTransport()
    twelve_transport = CountingTransport()
    identifiers = count(302001)
    creation = DailyMarketBarCreationService(
        sqlalchemy_uow_factory,
        UuidDailyMarketBarIDFactory(IdentifierFactory(lambda: UUID(int=next(identifiers)))),
    )
    alpaca = AlpacaDailyMarketBarIngestionService(
        AlpacaDailyMarketDataProvider(
            _ALPACA,
            alpaca_transport,
            AlpacaRequestRateLimiter(_ALPACA.requests_per_minute),
            clock,
        ),
        sqlalchemy_uow_factory,
        creation,
        clock,
        DailyMarketBarCalendarValidator(calendar),
    )
    twelve = TwelveDataDailyMarketBarIngestionService(
        TwelveDataDailyMarketDataProvider(
            _TWELVE,
            twelve_transport,
            TwelveDataCreditLimiter(
                credits_per_minute=_TWELVE.credits_per_minute,
                daily_credit_budget=_TWELVE.daily_credit_budget,
                clock=clock,
            ),
            clock,
        ),
        sqlalchemy_uow_factory,
        creation,
        clock,
        DailyMarketBarCalendarValidator(calendar),
    )
    request_values = {
        "symbol": Symbol("AAPL"),
        "mic_code": "XNGS",
        "adjustment_basis": DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        "as_of": clock.now_utc(),
        "requested_session_count": 30,
        "completion_grace": CompletionGracePeriod(timedelta(minutes=15)),
    }
    alpaca_request = request_factory.create(source_code=ALPACA_SOURCE_CODE, **request_values)
    twelve_request = request_factory.create(
        source_code=TWELVE_DATA_SOURCE_CODE,
        **request_values,
    )
    assert alpaca_request.outcome is CompletedDailyBarsRequestCreationOutcome.CREATED
    assert twelve_request.outcome is CompletedDailyBarsRequestCreationOutcome.CREATED
    assert alpaca_request.request is not None
    assert twelve_request.request is not None
    cutoff = alpaca_request.request.completed_through_session_date
    assert cutoff == twelve_request.request.completed_through_session_date
    assert cutoff is not None
    alpaca_result = alpaca.ingest(
        AlpacaDailyMarketBarIngestionCommand(
            Symbol("AAPL"),
            "XNGS",
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            cutoff,
            30,
        )
    )
    twelve_result = twelve.ingest(
        TwelveDataDailyMarketBarIngestionCommand(
            Symbol("AAPL"),
            "XNGS",
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            cutoff,
            30,
        )
    )

    assert alpaca_result.outcome is AlpacaIngestionOutcome.COMPLETED
    assert twelve_result.outcome is TwelveDataIngestionOutcome.COMPLETED
    assert len(alpaca_transport.calls) == 1
    assert len(twelve_transport.calls) == 1
    report = DailyBarProviderComparisonService(sqlalchemy_uow_factory).compare(
        CompareDailyBarProvidersCommand(
            TWELVE_DATA_SOURCE_CODE,
            ALPACA_SOURCE_CODE,
            Symbol("AAPL"),
            clock.now_utc(),
            30,
            21,
        )
    )
    assert report.outcome is DailyBarProviderComparisonOutcome.COMPARABLE
    assert report.overlap_count >= 21
    assert report.median_absolute_close_relative_difference is not None
    assert report.maximum_absolute_close_relative_difference is not None
    assert report.return_direction_observation_count >= 20
    assert report.return_direction_agreement_rate is not None
    with mssql_database.engine.connect() as connection:
        after = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in _SIDE_EFFECT_TABLES
        )
    assert after == before
    print(
        "DAILY_BAR_COMPARISON_LIVE_SAFE_RESULT "
        f"primary_requests={len(twelve_transport.calls)} "
        f"validation_requests={len(alpaca_transport.calls)} "
        f"overlap={report.overlap_count}"
    )
