from datetime import timedelta

import pytest

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data import HttpResponse
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataErrorCategory,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.feature_building import (
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.daily_market_bars.helpers import build_command, feature_service
from tests.integration.twelve_data.helpers import (
    API_KEY,
    OBSERVED_AT,
    ScriptedTransport,
    ingestion_command,
    ingestion_service,
    time_series_payload,
)

pytestmark = pytest.mark.integration


def test_scripted_contract_ingestion_retry_revision_and_degraded_feature(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    transport = ScriptedTransport(
        time_series_payload(),
        time_series_payload(),
        time_series_payload(revised_index=20),
    )
    clock = FixedClock(OBSERVED_AT)
    subject = ingestion_service(sqlalchemy_uow_factory, transport, clock, 271001)

    created = subject.ingest(ingestion_command())
    first_available = tuple(bar.bar_input.available_at for bar in created.bars)
    clock.advance(timedelta(hours=1))
    repeated = subject.ingest(ingestion_command())
    clock.advance(timedelta(hours=1))
    revised = subject.ingest(ingestion_command())

    assert created.outcome is TwelveDataIngestionOutcome.COMPLETED
    assert created.summary.created_count == 21
    assert repeated.outcome is TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING
    assert repeated.summary.existing_count == 21
    assert tuple(bar.bar_input.available_at for bar in repeated.bars) == first_available
    assert revised.summary.created_count == 1
    assert revised.summary.existing_count == 20
    request = transport.calls[0]
    query = dict(request.query)
    assert request.path == "/time_series"
    assert set(query) == {
        "adjust",
        "apikey",
        "end_date",
        "interval",
        "mic_code",
        "order",
        "outputsize",
        "symbol",
    }
    assert query["adjust"] == "splits"
    assert query["interval"] == "1day"
    assert query["mic_code"] == "XNAS"
    assert query["outputsize"] == "21"
    assert query["order"] == "asc"
    assert API_KEY not in repr(request)

    as_of = clock.now_utc()
    build = feature_service(sqlalchemy_uow_factory, as_of, 271999)
    source = build_command(271, as_of)
    source = type(source)(
        source_code=TWELVE_DATA_SOURCE_CODE,
        symbol=Symbol("AAPL"),
        as_of=as_of,
        horizon=source.horizon,
    )
    feature = build.build(source)
    retry = build.build(source)

    assert feature.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.CREATED
    assert retry.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.ALREADY_EXISTS
    assert feature.snapshot is not None
    snapshot = feature.snapshot.snapshot_input
    assert snapshot.quality_status is FeatureQualityStatus.DEGRADED
    assert snapshot.quality_reason_codes == ("VOLUME_DATA_INCOMPLETE",)
    assert snapshot.feature_values["volume_ratio_5_to_20"] is None
    assert snapshot.feature_values["latest_volume_to_avg20"] is None
    assert snapshot.feature_values["average_dollar_volume_20"] is None
    assert {entry.source_code for entry in snapshot.provenance} == {TWELVE_DATA_SOURCE_CODE}
    with sqlalchemy_uow_factory() as unit_of_work:
        recommendations = unit_of_work.recommendations.list_by_feature_snapshot_id(
            feature.snapshot.feature_snapshot_id
        )
    assert recommendations == ()


def test_scripted_transient_retry_and_provider_error_are_explicit(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    clock = FixedClock(OBSERVED_AT)
    retry_transport = ScriptedTransport(
        HttpResponse(429, (), b'{"status":"error","code":429}'),
        time_series_payload(),
    )
    completed = ingestion_service(
        sqlalchemy_uow_factory,
        retry_transport,
        clock,
        271101,
    ).ingest(ingestion_command())

    assert completed.outcome is TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING
    assert completed.summary.existing_count == 21
    assert len(retry_transport.calls) == 2

    error_transport = ScriptedTransport(
        {"status": "error", "code": 400, "message": "invalid symbol"},
    )
    rejected = ingestion_service(
        sqlalchemy_uow_factory,
        error_transport,
        clock,
        271201,
    ).ingest(ingestion_command())

    assert rejected.outcome is TwelveDataIngestionOutcome.PROVIDER_ERROR
    assert (
        rejected.summary.safe_error_category
        == TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST.value
    )
    assert len(error_transport.calls) == 1


def test_sqlalchemy_write_dotnet_source_identity_and_pit_read_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    clock = FixedClock(OBSERVED_AT)
    ingested = ingestion_service(
        sqlalchemy_uow_factory,
        ScriptedTransport(time_series_payload()),
        clock,
        272001,
    ).ingest(ingestion_command())
    expected = ingested.bars[-1]
    source = expected.bar_input

    with dotnet_uow_factory() as dotnet:
        by_identity = dotnet.daily_market_bars.get_by_source_identity(
            source.source_code,
            source.source_record_key,
            source.source_version,
        )
        latest = dotnet.daily_market_bars.list_latest_available(
            TWELVE_DATA_SOURCE_CODE,
            Symbol("AAPL"),
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            clock.now_utc(),
            21,
        )

    assert by_identity == expected
    assert latest == ingested.bars


def test_dotnet_write_sqlalchemy_read_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    clock = FixedClock(OBSERVED_AT)
    ingested = ingestion_service(
        dotnet_uow_factory,
        ScriptedTransport(time_series_payload()),
        clock,
        273001,
    ).ingest(ingestion_command())
    expected = ingested.bars[0]
    source = expected.bar_input

    with sqlalchemy_uow_factory() as sqlalchemy:
        actual = sqlalchemy.daily_market_bars.get_by_source_identity(
            source.source_code,
            source.source_record_key,
            source.source_version,
        )

    assert actual == expected
