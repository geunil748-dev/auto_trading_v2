"""Repository bindings for the P4A/P4B prediction persistence slice."""

from collections.abc import Callable

from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyDailyFeatureOutcomeObservationRunRepository,
    SqlAlchemyDailyFeatureOutcomeRepository,
    SqlAlchemyDailyFeatureScoringRunRepository,
)
from auto_trading_v2.application.errors import TransactionStateError

_RepositoryArgs = tuple[Connection, Callable[[], None], Callable[[], None]]


class SqlAlchemyPredictionUnitOfWorkMixin:
    _daily_feature_scoring_runs: SqlAlchemyDailyFeatureScoringRunRepository | None
    _daily_feature_outcomes: SqlAlchemyDailyFeatureOutcomeRepository | None
    _daily_feature_outcome_observation_runs: (
        SqlAlchemyDailyFeatureOutcomeObservationRunRepository | None
    )

    def _initialize_prediction_repository_slots(self) -> None:
        self._daily_feature_scoring_runs = None
        self._daily_feature_outcomes = None
        self._daily_feature_outcome_observation_runs = None

    def _bind_prediction_repositories(self, args: _RepositoryArgs) -> None:
        self._daily_feature_scoring_runs = SqlAlchemyDailyFeatureScoringRunRepository(*args)
        self._daily_feature_outcomes = SqlAlchemyDailyFeatureOutcomeRepository(*args)
        self._daily_feature_outcome_observation_runs = (
            SqlAlchemyDailyFeatureOutcomeObservationRunRepository(*args)
        )

    @property
    def daily_feature_scoring_runs(self) -> SqlAlchemyDailyFeatureScoringRunRepository:
        self._ensure_repository_operation()
        if self._daily_feature_scoring_runs is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_scoring_runs

    @property
    def daily_feature_outcomes(self) -> SqlAlchemyDailyFeatureOutcomeRepository:
        self._ensure_repository_operation()
        if self._daily_feature_outcomes is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_outcomes

    @property
    def daily_feature_outcome_observation_runs(
        self,
    ) -> SqlAlchemyDailyFeatureOutcomeObservationRunRepository:
        self._ensure_repository_operation()
        if self._daily_feature_outcome_observation_runs is None:
            raise TransactionStateError("repository_access")
        return self._daily_feature_outcome_observation_runs

    def _ensure_repository_operation(self) -> None:
        raise NotImplementedError
