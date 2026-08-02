"""Insert-only P4B.1 persistence with exact duplicate-race resolution."""

from dataclasses import dataclass
from enum import StrEnum

from auto_trading_v2.application.contracts.feature_outcomes import (
    NewDailyFeatureOutcome,
    NewDailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.application.feature_outcome_errors import (
    DailyFeatureOutcomeConflictError,
    DailyFeatureOutcomeObservationRunConflictError,
    DailyFeatureOutcomeObservationRunPersistenceError,
    DailyFeatureOutcomeObservationRunRaceResolutionError,
    DailyFeatureOutcomePersistenceError,
    DailyFeatureOutcomeRaceResolutionError,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcome,
    DailyFeatureOutcomeObservationRunWithItems,
)


class CanonicalOutcomeStoreDisposition(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class CanonicalOutcomeStoreResult:
    disposition: CanonicalOutcomeStoreDisposition
    outcome: DailyFeatureOutcome


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeStore:
    unit_of_work_factory: UnitOfWorkFactory

    def existing(self, outcome_key: str) -> DailyFeatureOutcome | None:
        with self.unit_of_work_factory() as unit_of_work:
            return unit_of_work.daily_feature_outcomes.get_by_outcome_key(outcome_key)

    def persist(self, candidate: NewDailyFeatureOutcome) -> CanonicalOutcomeStoreResult:
        existing = self.existing(candidate.outcome.outcome_key)
        if existing is not None:
            return self._same(existing, candidate)
        try:
            with self.unit_of_work_factory() as unit_of_work:
                try:
                    stored = unit_of_work.daily_feature_outcomes.add(candidate)
                except DuplicateRecordError:
                    unit_of_work.rollback()
                else:
                    unit_of_work.commit()
                    return CanonicalOutcomeStoreResult(
                        CanonicalOutcomeStoreDisposition.CREATED,
                        stored,
                    )
        except PersistenceError:
            raise DailyFeatureOutcomePersistenceError() from None
        existing = self.existing(candidate.outcome.outcome_key)
        if existing is None:
            raise DailyFeatureOutcomeRaceResolutionError()
        return self._same(existing, candidate)

    @staticmethod
    def _same(
        existing: DailyFeatureOutcome,
        candidate: NewDailyFeatureOutcome,
    ) -> CanonicalOutcomeStoreResult:
        if existing.content_digest != candidate.outcome.content_digest:
            raise DailyFeatureOutcomeConflictError()
        return CanonicalOutcomeStoreResult(
            CanonicalOutcomeStoreDisposition.ALREADY_EXISTS,
            existing,
        )


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeObservationRunStore:
    unit_of_work_factory: UnitOfWorkFactory

    def existing(self, run_key: str) -> DailyFeatureOutcomeObservationRunWithItems | None:
        with self.unit_of_work_factory() as unit_of_work:
            run = unit_of_work.daily_feature_outcome_observation_runs.get_by_observation_run_key(
                run_key
            )
            if run is None:
                return None
            aggregate = unit_of_work.daily_feature_outcome_observation_runs.get_run_with_items(
                run.daily_feature_outcome_observation_run_id
            )
        if aggregate is None:
            raise DailyFeatureOutcomeObservationRunPersistenceError()
        return aggregate

    def persist(
        self,
        candidate: NewDailyFeatureOutcomeObservationRunWithItems,
    ) -> tuple[bool, DailyFeatureOutcomeObservationRunWithItems]:
        try:
            with self.unit_of_work_factory() as unit_of_work:
                try:
                    stored = unit_of_work.daily_feature_outcome_observation_runs.add_run_with_items(
                        candidate
                    )
                except DuplicateRecordError:
                    unit_of_work.rollback()
                else:
                    unit_of_work.commit()
                    return True, stored
        except PersistenceError:
            raise DailyFeatureOutcomeObservationRunPersistenceError() from None
        existing = self.existing(candidate.aggregate.run.observation_run_key)
        if existing is None:
            raise DailyFeatureOutcomeObservationRunRaceResolutionError()
        if existing.run.content_digest != candidate.aggregate.run.content_digest:
            raise DailyFeatureOutcomeObservationRunConflictError()
        return False, existing
