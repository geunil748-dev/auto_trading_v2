"""Read-only P3 consumption and immutable P4A scoring orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from auto_trading_v2.application.contracts.feature_scoring import (
    DailyFeatureScoringExecutionOutcome,
    DailyFeatureScoringExecutionResult,
    NewDailyFeatureScoringRun,
    NewDailyFeatureScoringRunWithItems,
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.application.feature_scoring_errors import (
    DailyFeatureScoringPersistenceError,
)
from auto_trading_v2.application.ports.id_factory import (
    DailyFeatureScoringItemIDFactory,
    DailyFeatureScoringRunIDFactory,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_feature_scoring_builder import (
    build_scoring_items,
    prepare_scoring_item,
)
from auto_trading_v2.application.services.daily_feature_scoring_persistence import (
    DailyFeatureScoringRunStore,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    PIPELINE_CODE,
    PIPELINE_VERSION,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunStatus,
)
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringIdentity,
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRunStatus,
    daily_feature_scoring_content_digest,
    daily_feature_scoring_run_key,
    fixed_policy_values,
)
from auto_trading_v2.ports.clock import Clock

_SOURCE_PROVIDER = "TWELVE_DATA_TIME_SERIES"
_ELIGIBLE_STATUSES = frozenset(
    {
        DailyFeaturePipelineRunStatus.COMPLETED,
        DailyFeaturePipelineRunStatus.COMPLETED_WITH_WARNINGS,
        DailyFeaturePipelineRunStatus.COMPLETED_WITH_PARTIAL_FAILURES,
    }
)


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringService:
    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    run_id_factory: DailyFeatureScoringRunIDFactory
    item_id_factory: DailyFeatureScoringItemIDFactory

    def run(self, command: RunDailyFeatureScoringCommand) -> DailyFeatureScoringExecutionResult:
        source = self._source_run(command)
        if source is None:
            return _failure(
                DailyFeatureScoringExecutionOutcome.SOURCE_RUN_NOT_FOUND,
                "SOURCE_RUN_NOT_FOUND",
            )
        if source.status not in _ELIGIBLE_STATUSES or not _supported_source(source):
            return _failure(
                DailyFeatureScoringExecutionOutcome.SOURCE_RUN_NOT_ELIGIBLE,
                "SOURCE_RUN_NOT_ELIGIBLE",
            )
        identity = DailyFeatureScoringIdentity(
            command.daily_feature_pipeline_run_id,
            *fixed_policy_values(),
        )
        scoring_run_key = daily_feature_scoring_run_key(identity)
        store = DailyFeatureScoringRunStore(self.unit_of_work_factory)
        existing = store.existing(scoring_run_key)
        if existing is not None:
            return DailyFeatureScoringExecutionResult(
                DailyFeatureScoringExecutionOutcome.ALREADY_EXISTS,
                existing,
            )
        with self.unit_of_work_factory() as unit_of_work:
            source_aggregate = unit_of_work.daily_feature_pipeline_runs.get_run_with_items(
                source.daily_feature_pipeline_run_id
            )
            if source_aggregate is None:
                raise DailyFeatureScoringPersistenceError()
            prepared = tuple(
                prepare_scoring_item(
                    source,
                    item,
                    (
                        None
                        if item.outcome
                        not in {
                            DailyFeaturePipelineItemOutcome.READY,
                            DailyFeaturePipelineItemOutcome.DEGRADED,
                        }
                        or item.feature_snapshot_id is None
                        else unit_of_work.feature_snapshots.get_by_id(item.feature_snapshot_id)
                    ),
                )
                for item in source_aggregate.items
            )
        generated = self.clock.now_utc()
        run_id = self.run_id_factory.new()
        items = build_scoring_items(
            run_id,
            prepared,
            generated,
            self.item_id_factory,
        )
        ready = sum(item.outcome is DailyFeatureScoringItemOutcome.SCORED_READY for item in items)
        degraded = sum(
            item.outcome is DailyFeatureScoringItemOutcome.SCORED_DEGRADED for item in items
        )
        unscorable = len(items) - ready - degraded
        status = _status(ready + degraded, unscorable)
        provisional = NewDailyFeatureScoringRun(
            run_id,
            scoring_run_key,
            "0" * 64,
            identity,
            status,
            len(items),
            ready,
            degraded,
            unscorable,
            generated,
        )
        digest = daily_feature_scoring_content_digest(
            provisional.stored(generated),
            tuple(item.stored(generated) for item in items),
        )
        return store.persist(
            NewDailyFeatureScoringRunWithItems(
                NewDailyFeatureScoringRun(
                    run_id,
                    scoring_run_key,
                    digest,
                    identity,
                    status,
                    len(items),
                    ready,
                    degraded,
                    unscorable,
                    generated,
                ),
                items,
            )
        )

    def _source_run(self, command: RunDailyFeatureScoringCommand) -> DailyFeaturePipelineRun | None:
        with self.unit_of_work_factory() as unit_of_work:
            return unit_of_work.daily_feature_pipeline_runs.get_by_id(
                command.daily_feature_pipeline_run_id
            )


def _supported_source(run: DailyFeaturePipelineRun) -> bool:
    identity = run.identity
    return (
        identity.pipeline_code == PIPELINE_CODE
        and identity.pipeline_version == PIPELINE_VERSION
        and identity.feature_set_code == FEATURE_SET_CODE
        and identity.feature_set_version == FEATURE_SET_VERSION
        and identity.provider_code == _SOURCE_PROVIDER
        and identity.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
    )


def _status(scored: int, unscorable: int) -> DailyFeatureScoringRunStatus:
    if scored == 0:
        return DailyFeatureScoringRunStatus.NO_SCORABLE_ITEMS
    if unscorable:
        return DailyFeatureScoringRunStatus.COMPLETED_WITH_UNSCORABLE
    return DailyFeatureScoringRunStatus.COMPLETED


def _failure(
    outcome: DailyFeatureScoringExecutionOutcome,
    reason: str,
) -> DailyFeatureScoringExecutionResult:
    return DailyFeatureScoringExecutionResult(outcome, None, reason)
