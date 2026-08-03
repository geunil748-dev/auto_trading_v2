from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import (
    UuidDailyMarketBarIDFactory,
    UuidFeatureSnapshotIDFactory,
)
from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    NewDailyMarketBar,
)
from auto_trading_v2.application.feature_building import (
    BuildDailyPriceTechnicalFeatureSnapshotCommand,
    BuildDailyTechnicalFeatureSnapshotCommand,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import (
    DailyMarketBarCreationService,
    DailyPriceTechnicalFeatureSnapshotService,
    DailyTechnicalFeatureSnapshotService,
    FeatureSnapshotCreationService,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import (
    Currency,
    DailyMarketBarID,
    IdentifierFactory,
    SessionDate,
    Symbol,
)


def command(
    case: int,
    index: int,
    *,
    revision: str = "v1",
    available_delta: timedelta = timedelta(minutes=1),
    close_delta: Decimal = Decimal(0),
    volume: int | None = 1000,
) -> CreateDailyMarketBarCommand:
    session = date(2024, 1, 1) + timedelta(days=case * 30 + index)
    observed_at = datetime.combine(session, datetime.min.time(), tzinfo=UTC) + timedelta(hours=22)
    close = Decimal(100 + index) + close_delta
    return CreateDailyMarketBarCommand(
        source_code=f"P2_SOURCE_{case}",
        source_record_key=f"p2-{case}-{index}-{revision}",
        source_version=revision,
        symbol=Symbol("AAPL"),
        currency=Currency("USD"),
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        session_date=SessionDate(session),
        observed_at=observed_at,
        available_at=observed_at + available_delta,
        open_price=close - Decimal("0.5"),
        high_price=close + Decimal(2),
        low_price=close - Decimal(2),
        close_price=close,
        volume=None if volume is None else volume + index * 10,
    )


def new_bar(
    source: CreateDailyMarketBarCommand,
    identifier: int,
) -> NewDailyMarketBar:
    return NewDailyMarketBar(
        DailyMarketBarID(UUID(int=identifier)),
        daily_market_bar_key(source.bar_input),
        daily_market_bar_content_digest(source.bar_input),
        source.bar_input,
    )


def creation_service(
    unit_of_work_factory: UnitOfWorkFactory,
    identifier: int,
) -> DailyMarketBarCreationService:
    identifiers = IdentifierFactory(lambda: UUID(int=identifier))
    return DailyMarketBarCreationService(
        unit_of_work_factory,
        UuidDailyMarketBarIDFactory(identifiers),
    )


def persist_series(
    unit_of_work_factory: UnitOfWorkFactory,
    case: int,
    *,
    count: int = 21,
    volume_none_at: int | None = None,
) -> tuple[DailyMarketBar, ...]:
    stored: list[DailyMarketBar] = []
    with unit_of_work_factory() as unit_of_work:
        for index in range(count):
            source = command(
                case,
                index,
                volume=None if index == volume_none_at else 1000,
            )
            stored.append(
                unit_of_work.daily_market_bars.add(new_bar(source, case * 1000 + index + 1))
            )
        unit_of_work.commit()
    return tuple(stored)


def build_command(case: int, as_of: datetime) -> BuildDailyTechnicalFeatureSnapshotCommand:
    return BuildDailyTechnicalFeatureSnapshotCommand(
        source_code=f"P2_SOURCE_{case}",
        symbol=Symbol("AAPL"),
        as_of=as_of,
        horizon=TradingDayHorizon(3),
    )


def price_build_command(
    case: int,
    as_of: datetime,
) -> BuildDailyPriceTechnicalFeatureSnapshotCommand:
    return BuildDailyPriceTechnicalFeatureSnapshotCommand(
        source_code=f"P2_SOURCE_{case}",
        symbol=Symbol("AAPL"),
        as_of=as_of,
        horizon=TradingDayHorizon(3),
    )


def feature_service(
    unit_of_work_factory: UnitOfWorkFactory,
    as_of: datetime,
    identifier: int,
) -> DailyTechnicalFeatureSnapshotService:
    identifiers = IdentifierFactory(lambda: UUID(int=identifier))
    creation = FeatureSnapshotCreationService(
        unit_of_work_factory,
        FixedClock(as_of + timedelta(seconds=1)),
        UuidFeatureSnapshotIDFactory(identifiers),
    )
    return DailyTechnicalFeatureSnapshotService(unit_of_work_factory, creation)


def price_feature_service(
    unit_of_work_factory: UnitOfWorkFactory,
    as_of: datetime,
    identifier: int,
) -> DailyPriceTechnicalFeatureSnapshotService:
    identifiers = IdentifierFactory(lambda: UUID(int=identifier))
    creation = FeatureSnapshotCreationService(
        unit_of_work_factory,
        FixedClock(as_of + timedelta(seconds=1)),
        UuidFeatureSnapshotIDFactory(identifiers),
    )
    return DailyPriceTechnicalFeatureSnapshotService(unit_of_work_factory, creation)


def revised(
    source: CreateDailyMarketBarCommand,
    *,
    revision: str,
    available_at: datetime,
    close_delta: Decimal,
) -> CreateDailyMarketBarCommand:
    close = source.close_price + close_delta
    return replace(
        source,
        source_record_key=f"{source.source_record_key}-{revision}",
        source_version=revision,
        available_at=available_at,
        open_price=close - Decimal("0.5"),
        high_price=close + Decimal(2),
        low_price=close - Decimal(2),
        close_price=close,
    )


def assert_same_bar(actual: DailyMarketBar, expected: DailyMarketBar) -> None:
    assert actual.daily_market_bar_id == expected.daily_market_bar_id
    assert actual.bar_key == expected.bar_key
    assert actual.content_digest == expected.content_digest
    assert actual.bar_input == expected.bar_input
    assert actual.recorded_at == expected.recorded_at
