from datetime import UTC, datetime, timedelta

import pytest

from auto_trading_v2.adapters.clock import FixedClock, SystemClock
from auto_trading_v2.adapters.market_data import UrllibHttpTransport
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataCreditLimiter,
    TwelveDataDailyMarketDataProvider,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.feature_building import (
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.config import load_twelve_data_market_data_settings
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.daily_market_bars.helpers import build_command, feature_service
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


def test_live_aapl_split_adjusted_ingestion_and_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    system_clock = SystemClock()
    limiter = TwelveDataCreditLimiter(
        credits_per_minute=_SETTINGS.credits_per_minute,
        daily_credit_budget=_SETTINGS.daily_credit_budget,
        clock=system_clock,
    )
    provider = TwelveDataDailyMarketDataProvider(
        _SETTINGS,
        UrllibHttpTransport(),
        limiter,
        system_clock,
    )
    cutoff = system_clock.now_utc().date() - timedelta(days=10)
    live_command = type(ingestion_command())(
        symbol=Symbol("AAPL"),
        mic_code="XNAS",
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=type(ingestion_command().completed_through_session_date)(
            cutoff
        ),
        requested_session_count=30,
    )
    placeholder = ScriptedTransport()
    subject = ingestion_service(
        sqlalchemy_uow_factory,
        placeholder,
        FixedClock(datetime.now(UTC)),
        281001,
    )
    object.__setattr__(subject, "provider", provider)
    object.__setattr__(subject, "clock", system_clock)

    created = subject.ingest(live_command)
    repeated = subject.ingest(live_command)

    assert created.outcome is TwelveDataIngestionOutcome.COMPLETED
    assert created.summary.created_count >= 1
    assert repeated.outcome is TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING
    assert all(bar.bar_input.session_date.value <= cutoff for bar in created.bars)
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
        assert snapshot.feature_values["volume_ratio_5_to_20"] is None
        assert snapshot.feature_values["latest_volume_to_avg20"] is None
        assert snapshot.feature_values["average_dollar_volume_20"] is None
        with sqlalchemy_uow_factory() as sqlalchemy:
            recommendations = sqlalchemy.recommendations.list_by_feature_snapshot_id(
                result.snapshot.feature_snapshot_id
            )
        assert recommendations == ()
