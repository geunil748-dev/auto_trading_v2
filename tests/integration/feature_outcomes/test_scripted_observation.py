from decimal import Decimal

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.feature_outcomes import (
    DailyFeatureOutcomeObservationExecutionOutcome,
)
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcomeObservationRunItemOutcome,
    DailyFeatureOutcomeObservationRunStatus,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.feature_scoring import DailyFeatureScoringItemOutcome
from auto_trading_v2.domain.primitives import Symbol

from .helpers import (
    BEFORE_CORRECTION_AS_OF,
    FIRST_OBSERVATION_AS_OF,
    SECOND_OBSERVATION_AS_OF,
    observation_command,
    observation_service,
    seed_aapl_correction,
    seed_future_bars,
    seed_scoring,
)

pytestmark = pytest.mark.integration


def test_scripted_outcomes_retry_and_sqlalchemy_dotnet_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    scoring = seed_scoring(sqlalchemy_uow_factory, 1)
    seed_future_bars(sqlalchemy_uow_factory, 1)
    service = observation_service(sqlalchemy_uow_factory, 1)
    command = observation_command(scoring, FIRST_OBSERVATION_AS_OF)

    created = service.observe(command)  # type: ignore[arg-type]
    retried = service.observe(command)  # type: ignore[arg-type]

    assert created.outcome is DailyFeatureOutcomeObservationExecutionOutcome.CREATED
    assert created.result is not None
    assert created.result.run.status is DailyFeatureOutcomeObservationRunStatus.COMPLETED
    assert created.result.run.outcome_created_count == 2
    assert created.result.run.ineligible_count == 1
    assert created.result.items[-1].outcome is (
        DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE
    )
    assert retried.outcome is DailyFeatureOutcomeObservationExecutionOutcome.ALREADY_EXISTS
    assert retried.result == created.result
    observed_items = tuple(
        item
        for item in scoring.items
        if item.outcome
        in {
            DailyFeatureScoringItemOutcome.SCORED_READY,
            DailyFeatureScoringItemOutcome.SCORED_DEGRADED,
        }
    )
    nvda = next(item for item in scoring.items if item.symbol == Symbol("NVDA"))
    assert len(observed_items) == 2
    assert nvda.outcome is DailyFeatureScoringItemOutcome.SOURCE_ITEM_NOT_SCORABLE

    with sqlalchemy_uow_factory() as reader:
        sql_run = reader.daily_feature_outcome_observation_runs.get_run_with_items(
            created.result.run.daily_feature_outcome_observation_run_id
        )
        sql_outcomes = tuple(
            reader.daily_feature_outcomes.list_by_source_scoring_item(
                item.daily_feature_scoring_item_id
            )
            for item in observed_items
        )
    with dotnet_uow_factory() as reader:
        dotnet_run = reader.daily_feature_outcome_observation_runs.get_run_with_items(
            created.result.run.daily_feature_outcome_observation_run_id
        )
        dotnet_outcomes = tuple(
            reader.daily_feature_outcomes.list_by_source_scoring_item(
                item.daily_feature_scoring_item_id
            )
            for item in observed_items
        )

    assert sql_run == dotnet_run == created.result
    assert sql_outcomes == dotnet_outcomes
    assert all(len(values) == 1 for values in sql_outcomes)
    assert all(values[0].future_bar_count == 3 for values in sql_outcomes)
    assert all(
        values[0].observation_mode is OutcomeObservationMode.PROSPECTIVE for values in sql_outcomes
    )
    aapl = next(
        values[0]
        for item, values in zip(observed_items, sql_outcomes, strict=True)
        if item.symbol == Symbol("AAPL")
    )
    assert aapl.forward_close_return.value == Decimal("0.080000000000000000")
    assert aapl.maximum_favorable_excursion_rate.value == Decimal("0.100000000000000000")
    assert aapl.maximum_adverse_excursion_rate.value == Decimal("-0.050000000000000000")

    with sqlalchemy_uow_factory.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(recommendations)) == 0
        assert connection.scalar(select(func.count()).select_from(trade_intents)) == 0
        assert connection.scalar(select(func.count()).select_from(paper_orders)) == 0


def test_corrected_bar_creates_immutable_revision_and_latest_as_of_selection(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    scoring = seed_scoring(sqlalchemy_uow_factory, 2)
    seed_future_bars(sqlalchemy_uow_factory, 2)
    service = observation_service(sqlalchemy_uow_factory, 2)
    first = service.observe(  # type: ignore[arg-type]
        observation_command(scoring, FIRST_OBSERVATION_AS_OF)
    )
    assert first.result is not None
    aapl_item = next(item for item in scoring.items if item.symbol == Symbol("AAPL"))
    with sqlalchemy_uow_factory() as reader:
        original = reader.daily_feature_outcomes.list_by_source_scoring_item(
            aapl_item.daily_feature_scoring_item_id
        )[0]

    seed_aapl_correction(sqlalchemy_uow_factory, 2)
    second = service.observe(  # type: ignore[arg-type]
        observation_command(scoring, SECOND_OBSERVATION_AS_OF)
    )
    assert second.result is not None
    assert second.result.run.outcome_created_count == 1
    assert second.result.run.outcome_existing_count == 1
    assert second.result.run.ineligible_count == 1

    with sqlalchemy_uow_factory() as reader:
        revisions = reader.daily_feature_outcomes.list_by_source_scoring_item(
            aapl_item.daily_feature_scoring_item_id
        )
        before_correction = (
            reader.daily_feature_outcomes.get_latest_available_by_source_scoring_item(
                aapl_item.daily_feature_scoring_item_id,
                BEFORE_CORRECTION_AS_OF,
            )
        )
        after_correction = (
            reader.daily_feature_outcomes.get_latest_available_by_source_scoring_item(
                aapl_item.daily_feature_scoring_item_id,
                SECOND_OBSERVATION_AS_OF,
            )
        )

    assert len(revisions) == 2
    assert revisions[0] == original
    assert revisions[0].daily_feature_outcome_id != revisions[1].daily_feature_outcome_id
    assert revisions[0].outcome_key != revisions[1].outcome_key
    assert revisions[0].path_revision_digest != revisions[1].path_revision_digest
    assert before_correction == original
    assert after_correction == revisions[1]
    assert revisions[1].forward_close_return.value == Decimal("0.120000000000000000")
