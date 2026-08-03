"""Atomic persistence and duplicate-race recovery for P3 run aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    DailyFeaturePipelineExecutionOutcome,
    DailyFeaturePipelineExecutionResult,
    NewDailyFeaturePipelineItem,
    NewDailyFeaturePipelineRun,
    NewDailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.application.feature_pipeline_errors import (
    DailyFeaturePipelinePersistenceError,
    DailyFeaturePipelineRaceResolutionError,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_feature_pipeline_policy import outcome_counts
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineRunStatus,
    DailyFeaturePipelineRunWithItems,
    daily_feature_pipeline_content_digest,
)
from auto_trading_v2.domain.primitives import DailyFeaturePipelineRunID
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineRunStore:
    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock

    def existing(self, run_key: str) -> DailyFeaturePipelineRunWithItems | None:
        with self.unit_of_work_factory() as unit_of_work:
            run = unit_of_work.daily_feature_pipeline_runs.get_by_run_key(run_key)
            if run is None:
                return None
            aggregate = unit_of_work.daily_feature_pipeline_runs.get_run_with_items(
                run.daily_feature_pipeline_run_id
            )
        if aggregate is None:
            raise DailyFeaturePipelinePersistenceError()
        return aggregate

    def finalize(
        self,
        identity: DailyFeaturePipelineIdentity,
        run_key: str,
        run_id: DailyFeaturePipelineRunID,
        items: tuple[NewDailyFeaturePipelineItem, ...],
        status: DailyFeaturePipelineRunStatus,
        estimated: int | None,
        consumed: int | None,
        started: datetime,
    ) -> DailyFeaturePipelineExecutionResult:
        finished = self.clock.now_utc()
        counts = outcome_counts(tuple(item.outcome for item in items))
        provisional = self._new_run(
            identity,
            run_key,
            run_id,
            "0" * 64,
            status,
            len(items),
            counts,
            estimated,
            consumed,
            started,
            finished,
        )
        recorded_items = tuple(item.stored(finished) for item in items)
        digest = daily_feature_pipeline_content_digest(
            provisional.stored(finished),
            recorded_items,
        )
        aggregate = NewDailyFeaturePipelineRunWithItems(
            self._new_run(
                identity,
                run_key,
                run_id,
                digest,
                status,
                len(items),
                counts,
                estimated,
                consumed,
                started,
                finished,
            ),
            items,
        )
        return DailyFeaturePipelineExecutionResult(
            DailyFeaturePipelineExecutionOutcome.EXECUTED,
            self._persist(aggregate),
        )

    @staticmethod
    def _new_run(
        identity: DailyFeaturePipelineIdentity,
        run_key: str,
        run_id: DailyFeaturePipelineRunID,
        digest: str,
        status: DailyFeaturePipelineRunStatus,
        total_count: int,
        counts: dict[str, int],
        estimated: int | None,
        consumed: int | None,
        started: datetime,
        finished: datetime,
    ) -> NewDailyFeaturePipelineRun:
        return NewDailyFeaturePipelineRun(
            run_id,
            run_key,
            digest,
            identity,
            status,
            total_count,
            **counts,
            estimated_credit_count=estimated,
            consumed_credit_count=consumed,
            started_at=started,
            finished_at=finished,
        )

    def _persist(
        self,
        aggregate: NewDailyFeaturePipelineRunWithItems,
    ) -> DailyFeaturePipelineRunWithItems:
        try:
            with self.unit_of_work_factory() as unit_of_work:
                try:
                    stored = unit_of_work.daily_feature_pipeline_runs.add_run_with_items(aggregate)
                except DuplicateRecordError:
                    unit_of_work.rollback()
                else:
                    unit_of_work.commit()
                    return stored
        except PersistenceError:
            raise DailyFeaturePipelinePersistenceError() from None
        existing = self.existing(aggregate.run.run_key)
        if existing is None:
            raise DailyFeaturePipelineRaceResolutionError()
        return existing
