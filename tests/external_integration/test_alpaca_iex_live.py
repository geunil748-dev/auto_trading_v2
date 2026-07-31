from datetime import timedelta
from itertools import count
from uuid import UUID

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import SystemClock
from auto_trading_v2.adapters.identifiers import UuidDailyMarketBarIDFactory
from auto_trading_v2.adapters.market_data import (
    HttpRequest,
    HttpResponse,
    UrllibHttpTransport,
)
from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_SOURCE_CODE,
    AlpacaDailyMarketDataProvider,
    AlpacaProviderError,
    AlpacaRequestRateLimiter,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
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
from auto_trading_v2.application.ports.daily_market_data import (
    CompletedDailyMarketBarObservation,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.application.services import (
    AlpacaDailyMarketBarIngestionService,
    DailyMarketBarCreationService,
)
from auto_trading_v2.config import load_alpaca_market_data_settings
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import IdentifierFactory, SessionDate, Symbol
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.external_integration
_SETTINGS = load_alpaca_market_data_settings()
if not _SETTINGS.enabled or _SETTINGS.api_key_id is None or _SETTINGS.api_secret_key is None:
    pytestmark = [
        pytest.mark.external_integration,
        pytest.mark.skip(reason="Alpaca market-data credential is not configured"),
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


class CapturingProvider:
    def __init__(self, delegate: AlpacaDailyMarketDataProvider) -> None:
        self._delegate = delegate
        self.capabilities = delegate.capabilities
        self.last_error: AlpacaProviderError | None = None

    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[CompletedDailyMarketBarObservation, ...]:
        try:
            return self._delegate.fetch_completed_daily_bars(request)
        except AlpacaProviderError as error:
            self.last_error = error
            raise


def test_live_aapl_iex_split_ingestion_idempotency_and_parity(
    mssql_database: TemporaryMssqlDatabase,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    with mssql_database.engine.connect() as connection:
        before = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in _SIDE_EFFECT_TABLES
        )
    clock = SystemClock()
    transport = CountingTransport()
    provider = CapturingProvider(
        AlpacaDailyMarketDataProvider(
            _SETTINGS,
            transport,
            AlpacaRequestRateLimiter(_SETTINGS.requests_per_minute),
            clock,
        )
    )
    identifiers = count(301001)
    creation = DailyMarketBarCreationService(
        sqlalchemy_uow_factory,
        UuidDailyMarketBarIDFactory(IdentifierFactory(lambda: UUID(int=next(identifiers)))),
    )
    service = AlpacaDailyMarketBarIngestionService(
        provider,
        sqlalchemy_uow_factory,
        creation,
        clock,
    )
    cutoff = clock.now_utc().date() - timedelta(days=10)
    command = AlpacaDailyMarketBarIngestionCommand(
        symbol=Symbol("AAPL"),
        mic_code="XNGS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=SessionDate(cutoff),
        requested_session_count=30,
    )

    created = service.ingest(command)
    if created.outcome is not AlpacaIngestionOutcome.COMPLETED:
        error = provider.last_error
        pytest.fail(
            "ALPACA_LIVE_SAFE_FAILURE "
            f"category={created.summary.safe_error_category} "
            f"http_status={None if error is None else error.http_status} "
            f"provider_code={None if error is None else error.provider_code} "
            f"safe_parameter_hint={None if error is None else error.safe_parameter_hint} "
            f"retry_count={max(0, len(transport.calls) - 1)}"
        )
    repeated = service.ingest(command)

    assert len(created.bars) >= 21
    assert repeated.outcome is AlpacaIngestionOutcome.COMPLETED_WITH_EXISTING
    assert repeated.summary.existing_count == len(created.bars)
    assert len(transport.calls) == 2
    assert all(bar.bar_input.session_date.value <= cutoff for bar in created.bars)
    assert all(bar.bar_input.volume is not None for bar in created.bars)
    assert dict(transport.calls[0].query)["feed"] == "iex"
    assert dict(transport.calls[0].query)["adjustment"] == "split"
    assert "apikey" not in dict(transport.calls[0].query)
    latest = created.bars[-1]
    source = latest.bar_input
    with sqlalchemy_uow_factory() as sqlalchemy:
        sqlalchemy_read = sqlalchemy.daily_market_bars.get_by_source_identity(
            source.source_code,
            source.source_record_key,
            source.source_version,
        )
    with dotnet_uow_factory() as dotnet:
        dotnet_read = dotnet.daily_market_bars.get_by_source_identity(
            source.source_code,
            source.source_record_key,
            source.source_version,
        )
        latest_read = dotnet.daily_market_bars.list_latest_available(
            ALPACA_SOURCE_CODE,
            Symbol("AAPL"),
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            clock.now_utc(),
            30,
        )
    assert sqlalchemy_read == latest
    assert dotnet_read == latest
    assert latest_read == created.bars
    with mssql_database.engine.connect() as connection:
        after = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in _SIDE_EFFECT_TABLES
        )
    assert after == before
    print(
        f"ALPACA_LIVE_SAFE_RESULT requests={len(transport.calls)} parsed_rows={len(created.bars)}"
    )
