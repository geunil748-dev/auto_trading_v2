from datetime import timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.daily_market_bars import (
    DailyMarketBarCreationOutcome,
)
from auto_trading_v2.application.daily_market_bar_errors import (
    DailyMarketBarConflictError,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.primitives import Symbol
from tests.integration.daily_market_bars.helpers import (
    assert_same_bar,
    command,
    creation_service,
    new_bar,
    revised,
)

pytestmark = pytest.mark.integration


def test_sqlalchemy_create_read_retry_conflict_and_rollback(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    source = command(211, 0)
    service = creation_service(sqlalchemy_uow_factory, 211001)

    created = service.create(source)
    retried = service.create(source)

    assert created.outcome is DailyMarketBarCreationOutcome.CREATED
    assert retried.outcome is DailyMarketBarCreationOutcome.ALREADY_EXISTS
    assert_same_bar(retried.bar, created.bar)
    with sqlalchemy_uow_factory() as unit_of_work:
        assert (
            unit_of_work.daily_market_bars.get_by_id(created.bar.daily_market_bar_id) == created.bar
        )
        assert unit_of_work.daily_market_bars.get_by_bar_key(created.bar.bar_key) == created.bar
    with pytest.raises(DailyMarketBarConflictError):
        service.create(command(211, 0, close_delta=Decimal(1)))

    pending = new_bar(command(211, 1), 211002)
    with sqlalchemy_uow_factory() as unit_of_work:
        unit_of_work.daily_market_bars.add(pending)
    with sqlalchemy_uow_factory() as unit_of_work:
        assert unit_of_work.daily_market_bars.get_by_id(pending.daily_market_bar_id) is None


def test_sqlalchemy_latest_revision_distinct_limit_and_future_exclusion(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    originals = [command(212, index) for index in range(3)]
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
    sources = [*originals, latest, future]
    with sqlalchemy_uow_factory() as unit_of_work:
        stored = tuple(
            unit_of_work.daily_market_bars.add(new_bar(source, 212001 + index))
            for index, source in enumerate(sources)
        )
        unit_of_work.commit()

    with sqlalchemy_uow_factory() as unit_of_work:
        bars = unit_of_work.daily_market_bars.list_latest_available(
            "P2_SOURCE_212",
            Symbol("AAPL"),
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            cutoff,
            2,
        )

    assert len(bars) == 2
    assert tuple(bar.bar_input.session_date for bar in bars) == (
        originals[1].session_date,
        originals[2].session_date,
    )
    assert bars[-1].content_digest == stored[3].content_digest
    assert bars[-1].content_digest != stored[4].content_digest
