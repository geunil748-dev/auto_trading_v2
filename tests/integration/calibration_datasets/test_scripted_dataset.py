from datetime import UTC, datetime, timedelta
from itertools import count
from uuid import UUID

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import (
    UuidDailyFeatureOutcomeLabelIDFactory,
    UuidProbabilityCalibrationDatasetIDFactory,
    UuidProbabilityCalibrationDatasetItemIDFactory,
)
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyProbabilityCalibrationDatasetSourceReader,
)
from auto_trading_v2.adapters.persistence.tables import (
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    CreateProbabilityCalibrationDatasetCommand,
    ProbabilityCalibrationDatasetCreationOutcome,
)
from auto_trading_v2.application.contracts.outcome_labels import (
    CreateDailyFeatureOutcomeLabelCommand,
    DailyFeatureOutcomeLabelCreationOutcome,
)
from auto_trading_v2.application.services import (
    DailyFeatureOutcomeLabelCreationService,
    ProbabilityCalibrationDatasetCreationService,
)
from auto_trading_v2.domain.feature_scoring import DailyFeatureScoringItemOutcome
from auto_trading_v2.domain.outcome_labels import PositiveForwardCloseLabel
from auto_trading_v2.domain.primitives import IdentifierFactory, Symbol
from tests.integration.feature_outcomes.helpers import (
    FIRST_OBSERVATION_AS_OF,
    SECOND_OBSERVATION_AS_OF,
    observation_command,
    observation_service,
    seed_aapl_correction,
    seed_future_bars,
    seed_scoring,
)

pytestmark = pytest.mark.integration


def _label_service(
    factory: object,
    generated_at: datetime,
    seed: int,
) -> DailyFeatureOutcomeLabelCreationService:
    identifiers = count(seed)
    policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
    return DailyFeatureOutcomeLabelCreationService(
        factory,  # type: ignore[arg-type]
        FixedClock(generated_at),
        UuidDailyFeatureOutcomeLabelIDFactory(policy),
    )


def _dataset_service(
    factory: object,
    source_reader: SqlAlchemyProbabilityCalibrationDatasetSourceReader,
    generated_at: datetime,
    seed: int,
) -> ProbabilityCalibrationDatasetCreationService:
    identifiers = count(seed)
    policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
    return ProbabilityCalibrationDatasetCreationService(
        factory,  # type: ignore[arg-type]
        source_reader,
        _label_service(factory, generated_at, seed + 10_000),
        FixedClock(generated_at),
        UuidProbabilityCalibrationDatasetIDFactory(policy),
        UuidProbabilityCalibrationDatasetItemIDFactory(policy),
    )


def test_revision_cutoffs_labels_datasets_and_bidirectional_provider_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    scoring = seed_scoring(sqlalchemy_uow_factory, 40)
    seed_future_bars(sqlalchemy_uow_factory, 40)
    observer = observation_service(sqlalchemy_uow_factory, 40)
    first = observer.observe(observation_command(scoring, FIRST_OBSERVATION_AS_OF))  # type: ignore[arg-type]
    assert first.result is not None

    ready_item = next(
        item
        for item in scoring.items
        if item.outcome is DailyFeatureScoringItemOutcome.SCORED_READY
    )
    degraded_item = next(
        item
        for item in scoring.items
        if item.outcome is DailyFeatureScoringItemOutcome.SCORED_DEGRADED
    )
    with sqlalchemy_uow_factory() as reader:
        ready_original = reader.daily_feature_outcomes.list_by_source_scoring_item(
            ready_item.daily_feature_scoring_item_id
        )[0]
        degraded_outcome = reader.daily_feature_outcomes.list_by_source_scoring_item(
            degraded_item.daily_feature_scoring_item_id
        )[0]
    first_cutoff = max(ready_original.recorded_at, degraded_outcome.recorded_at)

    seed_aapl_correction(sqlalchemy_uow_factory, 40)
    second = observer.observe(observation_command(scoring, SECOND_OBSERVATION_AS_OF))  # type: ignore[arg-type]
    assert second.result is not None
    with sqlalchemy_uow_factory() as reader:
        ready_revisions = reader.daily_feature_outcomes.list_by_source_scoring_item(
            ready_item.daily_feature_scoring_item_id
        )
    assert len(ready_revisions) == 2
    ready_correction = ready_revisions[-1]
    assert ready_correction.recorded_at > first_cutoff

    label_generated_at = max(datetime.now(UTC), ready_correction.recorded_at)
    label_service = _label_service(sqlalchemy_uow_factory, label_generated_at, 1_040_000)
    labels = tuple(
        label_service.create(
            CreateDailyFeatureOutcomeLabelCommand(outcome.daily_feature_outcome_id)
        )
        for outcome in (*ready_revisions, degraded_outcome)
    )
    assert all(
        result.outcome is DailyFeatureOutcomeLabelCreationOutcome.CREATED for result in labels
    )
    assert labels[0].label.label_value is PositiveForwardCloseLabel.POSITIVE
    assert labels[-1].label.source_daily_feature_scoring_item_id == (
        degraded_item.daily_feature_scoring_item_id
    )

    after_cutoff = ready_correction.recorded_at + timedelta(microseconds=1)
    dotnet_cutoff = ready_correction.recorded_at + timedelta(microseconds=2)
    generated_at = max(datetime.now(UTC), dotnet_cutoff)
    with sqlalchemy_uow_factory.engine.connect() as connection:
        source_reader = SqlAlchemyProbabilityCalibrationDatasetSourceReader(connection)
        sql_service = _dataset_service(
            sqlalchemy_uow_factory, source_reader, generated_at, 1_050_000
        )
        before = sql_service.create(
            CreateProbabilityCalibrationDatasetCommand(ready_original.horizon, first_cutoff)
        )
        before_retry = sql_service.create(
            CreateProbabilityCalibrationDatasetCommand(ready_original.horizon, first_cutoff)
        )
        after = sql_service.create(
            CreateProbabilityCalibrationDatasetCommand(ready_original.horizon, after_cutoff)
        )
        dotnet_service = _dataset_service(
            dotnet_uow_factory, source_reader, generated_at, 1_060_000
        )
        dotnet_written = dotnet_service.create(
            CreateProbabilityCalibrationDatasetCommand(
                ready_original.horizon,
                dotnet_cutoff,
            )
        )

    assert before.outcome is ProbabilityCalibrationDatasetCreationOutcome.CREATED
    assert before_retry.outcome is ProbabilityCalibrationDatasetCreationOutcome.ALREADY_EXISTS
    assert before_retry.dataset == before.dataset
    assert after.outcome is ProbabilityCalibrationDatasetCreationOutcome.CREATED
    assert dotnet_written.outcome is ProbabilityCalibrationDatasetCreationOutcome.CREATED
    assert before.dataset.dataset.total_count == after.dataset.dataset.total_count == 1
    assert before.dataset.items[0].source_daily_feature_outcome_id == (
        ready_original.daily_feature_outcome_id
    )
    assert after.dataset.items[0].source_daily_feature_outcome_id == (
        ready_correction.daily_feature_outcome_id
    )
    assert all(item.source_quality_status.value == "READY" for item in after.dataset.items)
    assert all(item.symbol == Symbol("AAPL") for item in after.dataset.items)

    dataset_ids = (
        before.dataset.dataset.probability_calibration_dataset_id,
        after.dataset.dataset.probability_calibration_dataset_id,
        dotnet_written.dataset.dataset.probability_calibration_dataset_id,
    )
    with sqlalchemy_uow_factory() as sql_reader:
        sql_aggregates = tuple(
            sql_reader.probability_calibration_datasets.get_dataset_with_items(identifier)
            for identifier in dataset_ids
        )
        sql_labels = tuple(
            sql_reader.daily_feature_outcome_labels.get_by_id(
                result.label.daily_feature_outcome_label_id
            )
            for result in labels
        )
    with dotnet_uow_factory() as dotnet_reader:
        dotnet_aggregates = tuple(
            dotnet_reader.probability_calibration_datasets.get_dataset_with_items(identifier)
            for identifier in dataset_ids
        )
        dotnet_labels = tuple(
            dotnet_reader.daily_feature_outcome_labels.get_by_id(
                result.label.daily_feature_outcome_label_id
            )
            for result in labels
        )

    assert (
        sql_aggregates
        == dotnet_aggregates
        == (
            before.dataset,
            after.dataset,
            dotnet_written.dataset,
        )
    )
    assert sql_labels == dotnet_labels == tuple(result.label for result in labels)
    with sqlalchemy_uow_factory.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(recommendations)) == 0
        assert connection.scalar(select(func.count()).select_from(trade_intents)) == 0
        assert connection.scalar(select(func.count()).select_from(paper_orders)) == 0
