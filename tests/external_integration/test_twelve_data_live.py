from datetime import timedelta

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import FixedClock, SystemClock
from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.adapters.market_data import (
    HttpRequest,
    HttpResponse,
    UrllibHttpTransport,
)
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataCreditLimiter,
    TwelveDataDailyMarketDataProvider,
    TwelveDataProviderError,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    paper_orders as paper_orders_table,
)
from auto_trading_v2.adapters.persistence.tables import (
    recommendations as recommendations_table,
)
from auto_trading_v2.adapters.persistence.tables import (
    trade_intents as trade_intents_table,
)
from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationOutcome,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.feature_building import (
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.application.ports.daily_market_data import (
    CompletedDailyMarketBarObservation,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.application.services import (
    CompletedDailyBarsRequestFactory,
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.config import load_twelve_data_market_data_settings
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.daily_market_bars.helpers import build_command, feature_service
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.twelve_data.helpers import (
    ScriptedTransport,
    ingestion_command,
    ingestion_service,
)

pytestmark = pytest.mark.external_integration
_SETTINGS = load_twelve_data_market_data_settings()
if not _SETTINGS.enabled or _SETTINGS.api_key is None:
    pytestmark = [
        pytest.mark.external_integration,
        pytest.mark.skip(reason="Twelve Data credential is not configured"),
    ]

_PRICE_FEATURES = (
    "last_close",
    "one_day_return",
    "five_day_return",
    "twenty_day_return",
    "latest_gap_return",
    "latest_intraday_return",
    "latest_range_rate",
    "close_vs_sma5",
    "close_vs_sma10",
    "close_vs_sma20",
    "realized_volatility_20d",
    "atr14_rate",
    "distance_from_prior_20d_high",
    "distance_from_prior_20d_low",
)


class CountingHttpTransport:
    def __init__(self) -> None:
        self.calls = 0
        self._delegate = UrllibHttpTransport()

    def send(
        self,
        base_url: str,
        request: HttpRequest,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        self.calls += 1
        return self._delegate.send(
            base_url,
            request,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )


class SafeDiagnosticCapturingProvider:
    def __init__(self, delegate: TwelveDataDailyMarketDataProvider) -> None:
        self._delegate = delegate
        self.capabilities = delegate.capabilities
        self.last_error: TwelveDataProviderError | None = None

    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[CompletedDailyMarketBarObservation, ...]:
        try:
            return self._delegate.fetch_completed_daily_bars(request)
        except TwelveDataProviderError as error:
            self.last_error = error
            raise


def test_live_aapl_split_adjusted_ingestion_and_parity(
    mssql_database: TemporaryMssqlDatabase,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    system_clock = SystemClock()
    limiter = TwelveDataCreditLimiter(
        credits_per_minute=_SETTINGS.credits_per_minute,
        daily_credit_budget=_SETTINGS.daily_credit_budget,
        clock=system_clock,
    )
    transport = CountingHttpTransport()
    provider = SafeDiagnosticCapturingProvider(
        TwelveDataDailyMarketDataProvider(
            _SETTINGS,
            transport,
            limiter,
            system_clock,
        )
    )
    request_result = CompletedDailyBarsRequestFactory(
        UsEquityCompletedSessionResolver(StaticOfficialUsEquityCalendar2026())
    ).create(
        source_code=TWELVE_DATA_SOURCE_CODE,
        symbol=Symbol("AAPL"),
        mic_code="XNGS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        as_of=system_clock.now_utc(),
        requested_session_count=30,
        completion_grace=CompletionGracePeriod(timedelta(minutes=15)),
    )
    assert request_result.outcome is CompletedDailyBarsRequestCreationOutcome.CREATED
    assert request_result.request is not None
    cutoff = request_result.request.completed_through_session_date
    assert cutoff is not None
    live_command = type(ingestion_command())(
        symbol=Symbol("AAPL"),
        mic_code="XNGS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=cutoff,
        requested_session_count=30,
    )
    placeholder = ScriptedTransport()
    subject = ingestion_service(
        sqlalchemy_uow_factory,
        placeholder,
        FixedClock(system_clock.now_utc()),
        281001,
    )
    object.__setattr__(subject, "provider", provider)
    object.__setattr__(subject, "clock", system_clock)

    created = subject.ingest(live_command)
    if created.outcome is not TwelveDataIngestionOutcome.COMPLETED:
        error = provider.last_error
        pytest.fail(
            "TWELVE_DATA_LIVE_SAFE_FAILURE "
            f"category={created.summary.safe_error_category} "
            f"http_status={None if error is None else error.http_status} "
            f"provider_code={None if error is None else error.provider_code} "
            f"safe_parameter_hint={None if error is None else error.safe_parameter_hint} "
            f"retry_count={max(0, transport.calls - 1)}"
        )
    repeated = subject.ingest(live_command)

    assert created.summary.created_count >= 1
    assert repeated.outcome is TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING
    assert transport.calls == 2
    assert all(bar.bar_input.session_date.value <= cutoff.value for bar in created.bars)
    assert all(bar.bar_input.volume is None for bar in created.bars)
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
    assert sqlalchemy_read == latest
    assert dotnet_read == latest

    if len(created.bars) >= 21:
        as_of = system_clock.now_utc()
        build = feature_service(sqlalchemy_uow_factory, as_of, 281999)
        template = build_command(281, as_of)
        command = type(template)(
            source_code=TWELVE_DATA_SOURCE_CODE,
            symbol=Symbol("AAPL"),
            as_of=as_of,
            horizon=template.horizon,
        )
        result = build.build(command)
        assert result.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
        assert result.snapshot is not None
        snapshot = result.snapshot.snapshot_input
        assert snapshot.quality_status is FeatureQualityStatus.DEGRADED
        assert snapshot.quality_reason_codes == ("VOLUME_DATA_INCOMPLETE",)
        assert all(snapshot.feature_values[name] is not None for name in _PRICE_FEATURES)
        assert snapshot.feature_values["volume_ratio_5_to_20"] is None
        assert snapshot.feature_values["latest_volume_to_avg20"] is None
        assert snapshot.feature_values["average_dollar_volume_20"] is None
        with sqlalchemy_uow_factory() as sqlalchemy:
            recommendations = sqlalchemy.recommendations.list_by_feature_snapshot_id(
                result.snapshot.feature_snapshot_id
            )
        assert recommendations == ()

    with mssql_database.engine.connect() as connection:
        side_effect_counts = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in (
                recommendations_table,
                trade_intents_table,
                paper_orders_table,
            )
        )
    assert side_effect_counts == (0, 0, 0)

    oldest = created.bars[0].bar_input.session_date.serialize()
    newest = created.bars[-1].bar_input.session_date.serialize()
    print(
        "TWELVE_DATA_LIVE_SAFE_RESULT "
        f"requests={transport.calls} parsed_rows={len(created.bars)} "
        f"oldest_session={oldest} newest_session={newest}"
    )
