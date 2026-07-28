from datetime import timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.application.contracts.daily_market_bars import (
    DailyMarketBarCreationOutcome,
)
from auto_trading_v2.application.daily_market_bar_errors import (
    DailyMarketBarConflictError,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.daily_market_bars.helpers import (
    command,
    creation_service,
    new_bar,
    revised,
)

pytestmark = pytest.mark.integration


def test_dotnet_create_read_retry_conflict_and_rollback(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    source = command(221, 0)
    service = creation_service(dotnet_uow_factory, 221001)

    created = service.create(source)
    retried = service.create(source)

    assert created.outcome is DailyMarketBarCreationOutcome.CREATED
    assert retried.outcome is DailyMarketBarCreationOutcome.ALREADY_EXISTS
    with dotnet_uow_factory() as unit_of_work:
        assert (
            unit_of_work.daily_market_bars.get_by_id(created.bar.daily_market_bar_id) == created.bar
        )
    with pytest.raises(DailyMarketBarConflictError):
        service.create(command(221, 0, close_delta=Decimal(1)))

    pending = new_bar(command(221, 1), 221002)
    with dotnet_uow_factory() as unit_of_work:
        unit_of_work.daily_market_bars.add(pending)
    with dotnet_uow_factory() as unit_of_work:
        assert unit_of_work.daily_market_bars.get_by_id(pending.daily_market_bar_id) is None


def test_dotnet_reuses_core_latest_available_revision_query(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    originals = [command(222, index) for index in range(3)]
    cutoff = originals[2].available_at + timedelta(minutes=5)
    latest = revised(
        originals[2],
        revision="v2",
        available_at=cutoff - timedelta(minutes=1),
        close_delta=Decimal(2),
    )
    future = revised(
        originals[2],
        revision="v3",
        available_at=cutoff + timedelta(minutes=1),
        close_delta=Decimal(3),
    )
    with dotnet_uow_factory() as unit_of_work:
        stored = tuple(
            unit_of_work.daily_market_bars.add(new_bar(source, 222001 + index))
            for index, source in enumerate([*originals, latest, future])
        )
        unit_of_work.commit()
    with dotnet_uow_factory() as unit_of_work:
        bars = unit_of_work.daily_market_bars.list_latest_available(
            "P2_SOURCE_222",
            Symbol("AAPL"),
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            cutoff,
            2,
        )

    assert len(bars) == 2
    assert bars[-1].content_digest == stored[3].content_digest
    assert bars[-1].content_digest != stored[4].content_digest
