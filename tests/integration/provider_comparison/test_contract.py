import pytest

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_data.alpaca import ALPACA_SOURCE_CODE
from auto_trading_v2.adapters.market_data.twelve_data import TWELVE_DATA_SOURCE_CODE
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.contracts.daily_bar_comparison import (
    CompareDailyBarProvidersCommand,
    DailyBarProviderComparisonOutcome,
)
from auto_trading_v2.application.services import DailyBarProviderComparisonService
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.alpaca.helpers import (
    OBSERVED_AT,
    bars_payload,
)
from tests.integration.alpaca.helpers import (
    ScriptedTransport as AlpacaTransport,
)
from tests.integration.alpaca.helpers import (
    ingestion_command as alpaca_command,
)
from tests.integration.alpaca.helpers import (
    ingestion_service as alpaca_service,
)
from tests.integration.twelve_data.helpers import (
    ScriptedTransport as TwelveTransport,
)
from tests.integration.twelve_data.helpers import (
    ingestion_command as twelve_command,
)
from tests.integration.twelve_data.helpers import (
    ingestion_service as twelve_service,
)
from tests.integration.twelve_data.helpers import (
    time_series_payload,
)

pytestmark = pytest.mark.integration


def test_sqlalchemy_and_dotnet_produce_same_read_only_comparison_report(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    clock = FixedClock(OBSERVED_AT)
    twelve_service(
        sqlalchemy_uow_factory,
        TwelveTransport(time_series_payload()),
        clock,
        292001,
    ).ingest(twelve_command())
    alpaca_service(
        sqlalchemy_uow_factory,
        AlpacaTransport(bars_payload(close_delta=0.25)),
        clock,
        292101,
    ).ingest(alpaca_command())
    command = CompareDailyBarProvidersCommand(
        primary_source_code=TWELVE_DATA_SOURCE_CODE,
        validation_source_code=ALPACA_SOURCE_CODE,
        symbol=Symbol("AAPL"),
        as_of=clock.now_utc(),
        requested_session_count=21,
        minimum_overlap_sessions=21,
    )

    sqlalchemy_report = DailyBarProviderComparisonService(sqlalchemy_uow_factory).compare(command)
    dotnet_report = DailyBarProviderComparisonService(dotnet_uow_factory).compare(command)

    assert sqlalchemy_report == dotnet_report
    assert sqlalchemy_report.outcome is DailyBarProviderComparisonOutcome.COMPARABLE
    assert sqlalchemy_report.overlap_count == 21
    assert sqlalchemy_report.median_absolute_close_relative_difference is not None
    assert sqlalchemy_report.maximum_absolute_close_relative_difference is not None
    assert sqlalchemy_report.return_direction_observation_count == 20
    assert sqlalchemy_report.return_direction_agreement_rate is not None
