"""Atomic P4A persistence with exact duplicate-race resolution."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.feature_scoring import (
    DailyFeatureScoringExecutionOutcome,
    DailyFeatureScoringExecutionResult,
    NewDailyFeatureScoringRunWithItems,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.application.feature_scoring_errors import (
    DailyFeatureScoringConflictError,
    DailyFeatureScoringPersistenceError,
    DailyFeatureScoringRaceResolutionError,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.feature_scoring import DailyFeatureScoringRunWithItems


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringRunStore:
    unit_of_work_factory: UnitOfWorkFactory

    def existing(self, scoring_run_key: str) -> DailyFeatureScoringRunWithItems | None:
        with self.unit_of_work_factory() as unit_of_work:
            run = unit_of_work.daily_feature_scoring_runs.get_by_scoring_run_key(scoring_run_key)
            if run is None:
                return None
            aggregate = unit_of_work.daily_feature_scoring_runs.get_run_with_items(
                run.daily_feature_scoring_run_id
            )
        if aggregate is None:
            raise DailyFeatureScoringPersistenceError()
        return aggregate

    def persist(
        self, aggregate: NewDailyFeatureScoringRunWithItems
    ) -> DailyFeatureScoringExecutionResult:
        try:
            with self.unit_of_work_factory() as unit_of_work:
                try:
                    stored = unit_of_work.daily_feature_scoring_runs.add_run_with_items(aggregate)
                except DuplicateRecordError:
                    unit_of_work.rollback()
                else:
                    unit_of_work.commit()
                    return DailyFeatureScoringExecutionResult(
                        DailyFeatureScoringExecutionOutcome.CREATED,
                        stored,
                    )
        except PersistenceError:
            raise DailyFeatureScoringPersistenceError() from None
        existing = self.existing(aggregate.run.scoring_run_key)
        if existing is None:
            raise DailyFeatureScoringRaceResolutionError()
        if existing.run.content_digest != aggregate.run.content_digest:
            raise DailyFeatureScoringConflictError()
        return DailyFeatureScoringExecutionResult(
            DailyFeatureScoringExecutionOutcome.ALREADY_EXISTS,
            existing,
        )
