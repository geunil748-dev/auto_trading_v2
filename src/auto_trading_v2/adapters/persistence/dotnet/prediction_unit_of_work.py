"""DotNet repository bindings for the P4A/P4B prediction slice."""

from collections.abc import Callable

from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetDailyFeatureOutcomeLabelRepository,
    DotNetDailyFeatureOutcomeObservationRunRepository,
    DotNetDailyFeatureOutcomeRepository,
    DotNetDailyFeatureScoringRunRepository,
    DotNetProbabilityCalibrationDatasetRepository,
)
from auto_trading_v2.application.errors import TransactionStateError

_RepositoryArgs = tuple[Connection, Callable[[], None], Callable[[], None]]


class DotNetPredictionUnitOfWorkMixin:
    _daily_feature_scoring_runs: DotNetDailyFeatureScoringRunRepository | None
    _daily_feature_outcomes: DotNetDailyFeatureOutcomeRepository | None
    _daily_feature_outcome_observation_runs: (
        DotNetDailyFeatureOutcomeObservationRunRepository | None
    )
    _daily_feature_outcome_labels: DotNetDailyFeatureOutcomeLabelRepository | None
    _probability_calibration_datasets: DotNetProbabilityCalibrationDatasetRepository | None

    def _initialize_prediction_repository_slots(self) -> None:
        self._daily_feature_scoring_runs = None
        self._daily_feature_outcomes = None
        self._daily_feature_outcome_observation_runs = None
        self._daily_feature_outcome_labels = None
        self._probability_calibration_datasets = None

    def _bind_prediction_repositories(self, args: _RepositoryArgs) -> None:
        self._daily_feature_scoring_runs = DotNetDailyFeatureScoringRunRepository(*args)
        self._daily_feature_outcomes = DotNetDailyFeatureOutcomeRepository(*args)
        self._daily_feature_outcome_observation_runs = (
            DotNetDailyFeatureOutcomeObservationRunRepository(*args)
        )
        self._daily_feature_outcome_labels = DotNetDailyFeatureOutcomeLabelRepository(*args)
        self._probability_calibration_datasets = DotNetProbabilityCalibrationDatasetRepository(
            *args
        )

    @property
    def daily_feature_scoring_runs(self) -> DotNetDailyFeatureScoringRunRepository:
        self._ensure_repository_operation()
        if self._daily_feature_scoring_runs is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_scoring_runs

    @property
    def daily_feature_outcomes(self) -> DotNetDailyFeatureOutcomeRepository:
        self._ensure_repository_operation()
        if self._daily_feature_outcomes is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_outcomes

    @property
    def daily_feature_outcome_observation_runs(
        self,
    ) -> DotNetDailyFeatureOutcomeObservationRunRepository:
        self._ensure_repository_operation()
        if self._daily_feature_outcome_observation_runs is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_outcome_observation_runs

    @property
    def daily_feature_outcome_labels(self) -> DotNetDailyFeatureOutcomeLabelRepository:
        self._ensure_repository_operation()
        if self._daily_feature_outcome_labels is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_outcome_labels

    @property
    def probability_calibration_datasets(
        self,
    ) -> DotNetProbabilityCalibrationDatasetRepository:
        self._ensure_repository_operation()
        if self._probability_calibration_datasets is None:
            raise TransactionStateError("repository_access")
        return self._probability_calibration_datasets

    def _ensure_repository_operation(self) -> None:
        raise NotImplementedError
