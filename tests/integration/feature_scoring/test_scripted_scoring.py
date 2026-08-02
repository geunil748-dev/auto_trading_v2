from dataclasses import fields
from decimal import Decimal
from itertools import count
from uuid import UUID

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import (
    UuidDailyFeatureScoringItemIDFactory,
    UuidDailyFeatureScoringRunIDFactory,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.feature_scoring import (
    DailyFeatureScoringExecutionOutcome,
    NewDailyFeatureScoringItem,
    NewDailyFeatureScoringRun,
    NewDailyFeatureScoringRunWithItems,
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.services import DailyFeatureScoringService
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRunStatus,
)
from auto_trading_v2.domain.primitives import IdentifierFactory
from tests.integration.feature_pipeline.helpers import universe_command, universe_service
from tests.integration.feature_scoring.helpers import NOW, seed_source
from tests.integration.persistence.conftest import (
    temporary_dotnet_uow_factory,
    temporary_mssql_database,
)

pytestmark = pytest.mark.integration


def _new_aggregate(stored: object) -> NewDailyFeatureScoringRunWithItems:
    run_names = {field.name for field in fields(NewDailyFeatureScoringRun)}
    item_names = {field.name for field in fields(NewDailyFeatureScoringItem)}
    return NewDailyFeatureScoringRunWithItems(
        NewDailyFeatureScoringRun(**{name: getattr(stored.run, name) for name in run_names}),
        tuple(
            NewDailyFeatureScoringItem(**{name: getattr(item, name) for name in item_names})
            for item in stored.items
        ),
    )


def test_scripted_scoring_write_retry_and_dotnet_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    universe = (
        universe_service(sqlalchemy_uow_factory, 909_001)
        .create(universe_command(909, "META", "NVDA", "MSFT", "AMZN", "AAPL"))
        .snapshot
    )
    source_run_id = seed_source(sqlalchemy_uow_factory, universe)
    identifiers = count(920_000)
    id_policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
    service = DailyFeatureScoringService(
        sqlalchemy_uow_factory,
        FixedClock(NOW),
        UuidDailyFeatureScoringRunIDFactory(id_policy),
        UuidDailyFeatureScoringItemIDFactory(id_policy),
    )
    command = RunDailyFeatureScoringCommand(source_run_id)

    created = service.run(command)
    next_id_after_create = next(identifiers)
    retried = service.run(command)

    assert created.outcome is DailyFeatureScoringExecutionOutcome.CREATED
    assert created.result is not None
    assert created.result.run.status is DailyFeatureScoringRunStatus.COMPLETED_WITH_UNSCORABLE
    assert (
        created.result.run.scored_ready_count,
        created.result.run.scored_degraded_count,
        created.result.run.unscorable_count,
    ) == (2, 1, 2)
    assert [item.outcome for item in created.result.items] == [
        DailyFeatureScoringItemOutcome.SCORED_READY,
        DailyFeatureScoringItemOutcome.SCORED_READY,
        DailyFeatureScoringItemOutcome.SCORED_DEGRADED,
        DailyFeatureScoringItemOutcome.SOURCE_ITEM_NOT_SCORABLE,
        DailyFeatureScoringItemOutcome.SOURCE_ITEM_NOT_SCORABLE,
    ]
    assert [item.rank for item in created.result.items] == [2, 1, 3, None, None]
    assert created.result.items[2].volume_score is None
    assert retried.outcome is DailyFeatureScoringExecutionOutcome.ALREADY_EXISTS
    assert retried.result == created.result
    assert next(identifiers) == next_id_after_create + 1

    with sqlalchemy_uow_factory() as reader:
        sqlalchemy_read = reader.daily_feature_scoring_runs.get_run_with_items(
            created.result.run.daily_feature_scoring_run_id
        )
    with dotnet_uow_factory() as reader:
        dotnet_read = reader.daily_feature_scoring_runs.get_run_with_items(
            created.result.run.daily_feature_scoring_run_id
        )
    assert sqlalchemy_read == created.result
    assert dotnet_read == created.result
    assert dotnet_read == sqlalchemy_read
    with sqlalchemy_uow_factory.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(recommendations)) == 0
        assert connection.scalar(select(func.count()).select_from(trade_intents)) == 0
        assert connection.scalar(select(func.count()).select_from(paper_orders)) == 0


def test_dotnet_write_sqlalchemy_read_decimal_order_and_duplicate_rollback() -> None:
    with temporary_mssql_database() as database:
        sqlalchemy_factory = SqlAlchemyUnitOfWorkFactory(database.engine)
        with temporary_dotnet_uow_factory(database) as dotnet_factory:
            universe = (
                universe_service(sqlalchemy_factory, 930_001)
                .create(universe_command(930, "META", "NVDA", "MSFT", "AMZN", "AAPL"))
                .snapshot
            )
            source_run_id = seed_source(sqlalchemy_factory, universe)
            identifiers = count(940_000)
            id_policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
            service = DailyFeatureScoringService(
                dotnet_factory,
                FixedClock(NOW),
                UuidDailyFeatureScoringRunIDFactory(id_policy),
                UuidDailyFeatureScoringItemIDFactory(id_policy),
            )

            created = service.run(RunDailyFeatureScoringCommand(source_run_id))
            assert created.outcome is DailyFeatureScoringExecutionOutcome.CREATED
            assert created.result is not None

            with sqlalchemy_factory() as reader:
                sqlalchemy_read = reader.daily_feature_scoring_runs.get_run_with_items(
                    created.result.run.daily_feature_scoring_run_id
                )
            assert sqlalchemy_read == created.result
            assert [item.ordinal for item in sqlalchemy_read.items] == [1, 2, 3, 4, 5]
            scores = [
                item.overall_relative_score.value
                for item in sqlalchemy_read.items
                if item.overall_relative_score is not None
            ]
            assert scores and all(isinstance(score, Decimal) for score in scores)
            assert all(score.as_tuple().exponent == -6 for score in scores)
            assert sqlalchemy_read.items[2].volume_score is None
            assert all(item.overall_relative_score is None for item in sqlalchemy_read.items[3:])

            duplicate = _new_aggregate(created.result)
            with pytest.raises(DuplicateRecordError), dotnet_factory() as writer:
                writer.daily_feature_scoring_runs.add_run_with_items(duplicate)

            with sqlalchemy_factory() as reader:
                after_rollback = reader.daily_feature_scoring_runs.get_run_with_items(
                    created.result.run.daily_feature_scoring_run_id
                )
            assert after_rollback == created.result
