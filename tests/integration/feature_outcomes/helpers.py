from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import count
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import (
    UuidDailyFeatureOutcomeIDFactory,
    UuidDailyFeatureOutcomeObservationRunIDFactory,
    UuidDailyFeatureOutcomeObservationRunItemIDFactory,
    UuidDailyFeatureScoringItemIDFactory,
    UuidDailyFeatureScoringRunIDFactory,
)
from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.application.contracts.feature_outcomes import (
    ObserveDailyFeatureScoringOutcomesCommand,
)
from auto_trading_v2.application.contracts.feature_scoring import (
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import (
    DailyFeatureOutcomeObservationService,
    DailyFeatureScoringService,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod, MarketSession
from auto_trading_v2.domain.primitives import (
    Currency,
    DailyMarketBarID,
    IdentifierFactory,
    SessionDate,
    Symbol,
)
from tests.integration.feature_pipeline.helpers import universe_command, universe_service
from tests.integration.feature_scoring.helpers import seed_source

SOURCE_SESSION = SessionDate(date(2026, 7, 27))
SOURCE_SESSION_AS_OF = datetime(2026, 7, 28, 12, tzinfo=UTC)
FIRST_OBSERVATION_AS_OF = datetime(2026, 7, 31, tzinfo=UTC)
BEFORE_CORRECTION_AS_OF = datetime(2026, 7, 31, 11, tzinfo=UTC)
SECOND_OBSERVATION_AS_OF = datetime(2026, 8, 1, tzinfo=UTC)


def seed_scoring(factory: UnitOfWorkFactory, case: int) -> object:
    source_created_at = SOURCE_SESSION_AS_OF + timedelta(minutes=case)
    universe = (
        universe_service(
            factory,
            951_001 + case,
            source_created_at - timedelta(hours=1),
        )
        .create(universe_command(951 + case, "NVDA", "MSFT", "AAPL"))
        .snapshot
    )
    pipeline_run_id = seed_source(
        factory,
        universe,
        horizon=3,
        session=SOURCE_SESSION,
        now=source_created_at,
        case=case,
        outcome_observation_shape=True,
    )
    identifiers = count(952_000 + case * 100)
    policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
    result = DailyFeatureScoringService(
        factory,
        FixedClock(source_created_at),
        UuidDailyFeatureScoringRunIDFactory(policy),
        UuidDailyFeatureScoringItemIDFactory(policy),
    ).run(RunDailyFeatureScoringCommand(pipeline_run_id))
    assert result.result is not None
    return result.result


def future_sessions() -> tuple[MarketSession, ...]:
    sessions = StaticOfficialUsEquityCalendar2026().sessions("XNGS")
    index = next(
        index for index, session in enumerate(sessions) if session.session_date == SOURCE_SESSION
    )
    return sessions[index + 1 : index + 4]


def seed_future_bars(factory: UnitOfWorkFactory, case: int) -> None:
    prices = {
        "AAPL": (("101", "104", "97"), ("105", "107", "98"), ("108", "110", "95")),
        "MSFT": (("99", "101", "96"), ("97", "100", "92"), ("95", "99", "90")),
    }
    with factory() as unit_of_work:
        for symbol_index, (symbol, path) in enumerate(prices.items(), 1):
            for ordinal, (close, high, low) in enumerate(path, 1):
                session = future_sessions()[ordinal - 1]
                candidate = _bar(
                    960_000 + case * 100 + symbol_index * 10 + ordinal,
                    symbol,
                    session,
                    close,
                    high,
                    low,
                    version="v1",
                    available_at=session.close_at + timedelta(hours=2, seconds=case),
                    case=case,
                )
                unit_of_work.daily_market_bars.add(candidate)
        unit_of_work.commit()


def seed_aapl_correction(factory: UnitOfWorkFactory, case: int) -> None:
    terminal = future_sessions()[-1]
    candidate = _bar(
        961_999 + case,
        "AAPL",
        terminal,
        "112",
        "114",
        "94",
        version="v2-corrected",
        available_at=datetime(2026, 7, 31, 12, tzinfo=UTC) + timedelta(seconds=case),
        case=case,
    )
    with factory() as unit_of_work:
        unit_of_work.daily_market_bars.add(candidate)
        unit_of_work.commit()


def observation_service(
    factory: UnitOfWorkFactory,
    case: int,
) -> DailyFeatureOutcomeObservationService:
    identifiers = count(970_000 + case * 100)
    policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
    return DailyFeatureOutcomeObservationService(
        factory,
        StaticOfficialUsEquityCalendar2026(),
        FixedClock(SECOND_OBSERVATION_AS_OF + timedelta(seconds=1)),
        UuidDailyFeatureOutcomeIDFactory(policy),
        UuidDailyFeatureOutcomeObservationRunIDFactory(policy),
        UuidDailyFeatureOutcomeObservationRunItemIDFactory(policy),
    )


def observation_command(scoring: object, as_of: datetime) -> object:
    return ObserveDailyFeatureScoringOutcomesCommand(
        scoring.run.daily_feature_scoring_run_id,  # type: ignore[union-attr]
        as_of,
        CompletionGracePeriod(timedelta(minutes=15)),
    )


def _bar(
    identifier: int,
    symbol: str,
    session: MarketSession,
    close: str,
    high: str,
    low: str,
    *,
    version: str,
    available_at: datetime,
    case: int,
) -> NewDailyMarketBar:
    source = DailyMarketBarInput(
        "TWELVE_DATA_TIME_SERIES",
        f"p4b1-{case}-{symbol}-{session.session_date.serialize()}-{version}",
        version,
        Symbol(symbol),
        Currency("USD"),
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        session.session_date,
        available_at - timedelta(minutes=5),
        available_at,
        Decimal(close),
        Decimal(high),
        Decimal(low),
        Decimal(close),
        1_000_000,
    )
    return NewDailyMarketBar(
        DailyMarketBarID(UUID(int=identifier)),
        daily_market_bar_key(source),
        daily_market_bar_content_digest(source),
        source,
    )
