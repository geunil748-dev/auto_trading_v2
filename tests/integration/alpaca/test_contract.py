from datetime import timedelta

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data import HttpResponse
from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_SOURCE_CODE,
    AlpacaErrorCategory,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    feature_snapshots,
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.alpaca_ingestion import AlpacaIngestionOutcome
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.alpaca.helpers import (
    KEY_ID,
    OBSERVED_AT,
    SECRET,
    ScriptedTransport,
    bars_payload,
    ingestion_command,
    ingestion_service,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration
_SIDE_EFFECT_TABLES = (feature_snapshots, recommendations, trade_intents, paper_orders)


def test_scripted_ingestion_retry_revision_parity_and_no_trading_side_effects(
    mssql_database: TemporaryMssqlDatabase,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    with mssql_database.engine.connect() as connection:
        before = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in _SIDE_EFFECT_TABLES
        )
    transport = ScriptedTransport(
        bars_payload(),
        bars_payload(),
        bars_payload(revised_index=20),
    )
    clock = FixedClock(OBSERVED_AT)
    subject = ingestion_service(sqlalchemy_uow_factory, transport, clock, 291001)

    created = subject.ingest(ingestion_command())
    first_available = tuple(bar.bar_input.available_at for bar in created.bars)
    clock.advance(timedelta(hours=1))
    repeated = subject.ingest(ingestion_command())
    clock.advance(timedelta(hours=1))
    revised = subject.ingest(ingestion_command())

    assert created.outcome is AlpacaIngestionOutcome.COMPLETED
    assert created.summary.created_count == 21
    assert created.summary.source_feed == "iex"
    assert repeated.outcome is AlpacaIngestionOutcome.COMPLETED_WITH_EXISTING
    assert repeated.summary.existing_count == 21
    assert tuple(bar.bar_input.available_at for bar in repeated.bars) == first_available
    assert revised.summary.created_count == 1
    assert revised.summary.existing_count == 20
    assert all(bar.bar_input.volume is not None for bar in created.bars)
    request = transport.calls[0]
    query = dict(request.query)
    assert request.path == "/v2/stocks/AAPL/bars"
    assert query["timeframe"] == "1Day"
    assert query["feed"] == "iex"
    assert query["adjustment"] == "split"
    assert query["currency"] == "USD"
    assert query["sort"] == "asc"
    assert "mic_code" not in query
    assert "apikey" not in query
    assert request.headers == (
        ("APCA-API-KEY-ID", KEY_ID),
        ("APCA-API-SECRET-KEY", SECRET),
    )
    assert KEY_ID not in repr(request)
    assert SECRET not in repr(request)

    expected = revised.bars[-1]
    source = expected.bar_input
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
        latest = dotnet.daily_market_bars.list_latest_available(
            ALPACA_SOURCE_CODE,
            Symbol("AAPL"),
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            clock.now_utc(),
            21,
        )
    assert sqlalchemy_read == expected
    assert dotnet_read == expected
    assert latest == revised.bars

    with mssql_database.engine.connect() as connection:
        after = tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in _SIDE_EFFECT_TABLES
        )
    assert after == before


def test_scripted_pagination_429_retry_and_safe_403(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    full = bars_payload()
    rows = full["bars"]
    assert isinstance(rows, list)
    first_page = {
        "bars": rows[:10],
        "symbol": "AAPL",
        "next_page_token": "opaque-continuation",
    }
    second_page = {
        "bars": rows[10:],
        "symbol": "AAPL",
        "next_page_token": None,
    }
    transport = ScriptedTransport(
        HttpResponse(429, (), b'{"code":42910000}'),
        first_page,
        second_page,
    )
    clock = FixedClock(OBSERVED_AT)

    completed = ingestion_service(
        sqlalchemy_uow_factory,
        transport,
        clock,
        291501,
    ).ingest(ingestion_command())

    assert completed.outcome in {
        AlpacaIngestionOutcome.COMPLETED,
        AlpacaIngestionOutcome.COMPLETED_WITH_EXISTING,
    }
    assert completed.summary.fetched_count == 21
    assert len(transport.calls) == 3
    assert "page_token" not in dict(transport.calls[0].query)
    assert dict(transport.calls[2].query)["page_token"] == "opaque-continuation"
    assert "opaque-continuation" not in repr(transport.calls[2])

    forbidden = ingestion_service(
        sqlalchemy_uow_factory,
        ScriptedTransport(
            HttpResponse(
                403,
                (),
                b'{"code":40310000,"message":"feed entitlement secret sentinel"}',
            )
        ),
        clock,
        291601,
    ).ingest(ingestion_command())
    assert forbidden.outcome is AlpacaIngestionOutcome.PROVIDER_ERROR
    assert forbidden.summary.safe_error_category == AlpacaErrorCategory.ACCESS_FORBIDDEN.value
    assert "sentinel" not in repr(forbidden)
