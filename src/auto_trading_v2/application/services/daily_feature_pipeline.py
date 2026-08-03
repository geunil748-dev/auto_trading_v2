"""Sequential one-provider P3 daily feature pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataErrorCategory,
)
from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationOutcome,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    DailyFeaturePipelineExecutionOutcome,
    DailyFeaturePipelineExecutionResult,
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.feature_pipeline_errors import (
    UniverseSnapshotNotFoundError,
)
from auto_trading_v2.application.ports.batch_budget import (
    DailyMarketDataBatchBudgetPort,
    DailyMarketDataProviderRole,
)
from auto_trading_v2.application.ports.id_factory import (
    DailyFeaturePipelineItemIDFactory,
    DailyFeaturePipelineRunIDFactory,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.completed_daily_bars_request import (
    CompletedDailyBarsRequestFactory,
)
from auto_trading_v2.application.services.daily_feature_pipeline_executor import (
    PreparedPipelineMember,
    SequentialDailyFeaturePipelineExecutor,
    credit_delta,
)
from auto_trading_v2.application.services.daily_feature_pipeline_persistence import (
    DailyFeaturePipelineRunStore,
)
from auto_trading_v2.application.services.daily_feature_pipeline_policy import (
    assess_budget,
    completed_run_status,
)
from auto_trading_v2.application.services.daily_price_technical_feature_snapshot import (
    DailyPriceTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.daily_technical_feature_snapshot import (
    DailyTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    DAILY_FEATURE_PIPELINE_POLICY_V1,
    DAILY_FEATURE_PIPELINE_POLICY_V2,
    TRANSIENT_FAILURE_LIMIT,
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
    daily_feature_run_key,
)
from auto_trading_v2.domain.universes import UniverseSnapshot
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineService:
    unit_of_work_factory: UnitOfWorkFactory
    request_factory: CompletedDailyBarsRequestFactory
    budget: DailyMarketDataBatchBudgetPort
    ingestion_service: TwelveDataDailyMarketBarIngestionService
    feature_service: DailyTechnicalFeatureSnapshotService
    clock: Clock
    run_id_factory: DailyFeaturePipelineRunIDFactory
    item_id_factory: DailyFeaturePipelineItemIDFactory
    transient_failure_limit: int = field(default=TRANSIENT_FAILURE_LIMIT)
    price_feature_service: DailyPriceTechnicalFeatureSnapshotService | None = None

    def run(
        self,
        command: RunDailyFeaturePipelineCommand,
    ) -> DailyFeaturePipelineExecutionResult:
        universe = self._universe(command)
        prepared = self._prepare(universe, command)
        identity = self._identity(command, prepared)
        run_key = daily_feature_run_key(identity)
        store = self._store()
        existing = store.existing(run_key)
        if existing is not None:
            return DailyFeaturePipelineExecutionResult(
                DailyFeaturePipelineExecutionOutcome.ALREADY_EXISTS,
                existing,
            )
        run_id = self.run_id_factory.new()
        executor = self._executor(command)
        started = self.clock.now_utc()
        calendar_outcomes = tuple(entry.result.outcome for entry in prepared)
        if all(
            value is CompletedDailyBarsRequestCreationOutcome.NO_COMPLETED_SESSION
            for value in calendar_outcomes
        ):
            items = executor.not_attempted(
                run_id,
                prepared,
                DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED,
                "NO_COMPLETED_SESSION",
            )
            return store.finalize(
                identity,
                run_key,
                run_id,
                items,
                DailyFeaturePipelineRunStatus.NO_COMPLETED_SESSION,
                None,
                0,
                started,
            )
        if any(
            value is CompletedDailyBarsRequestCreationOutcome.CALENDAR_OUT_OF_COVERAGE
            for value in calendar_outcomes
        ):
            items = executor.not_attempted(
                run_id,
                prepared,
                DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED,
                "CALENDAR_OUT_OF_COVERAGE",
            )
            return store.finalize(
                identity,
                run_key,
                run_id,
                items,
                DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL,
                None,
                0,
                started,
            )
        provider_reason = self._provider_preflight_reason(command)
        if provider_reason is not None:
            items = executor.not_attempted(
                run_id,
                prepared,
                DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED,
                provider_reason,
            )
            return store.finalize(
                identity,
                run_key,
                run_id,
                items,
                DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL,
                None,
                0,
                started,
            )
        budget = assess_budget(self.budget, len(universe.members), command.requested_session_count)
        if not budget.can_start:
            items = executor.not_attempted(
                run_id,
                prepared,
                DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET,
                "PROVIDER_DAILY_BUDGET_BLOCKED",
            )
            return store.finalize(
                identity,
                run_key,
                run_id,
                items,
                DailyFeaturePipelineRunStatus.BUDGET_BLOCKED,
                budget.estimated_credits,
                0,
                started,
            )
        consumed_before = self.budget.consumed_daily_credits()
        items, fatal = executor.execute(run_id, prepared, command)
        consumed_after = self.budget.consumed_daily_credits()
        consumed = credit_delta(consumed_before, consumed_after)
        status = (
            DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL
            if fatal
            else completed_run_status(tuple(item.outcome for item in items))
        )
        return store.finalize(
            identity,
            run_key,
            run_id,
            items,
            status,
            budget.estimated_credits,
            consumed,
            started,
        )

    def _universe(self, command: RunDailyFeaturePipelineCommand) -> UniverseSnapshot:
        with self.unit_of_work_factory() as unit_of_work:
            universe = unit_of_work.universe_snapshots.get_by_id(command.universe_snapshot_id)
        if universe is None:
            raise UniverseSnapshotNotFoundError()
        return universe

    def _prepare(
        self,
        universe: UniverseSnapshot,
        command: RunDailyFeaturePipelineCommand,
    ) -> tuple[PreparedPipelineMember, ...]:
        return tuple(
            PreparedPipelineMember(
                member,
                self.request_factory.create(
                    source_code=command.provider_code,
                    symbol=member.symbol,
                    mic_code=member.mic_code,
                    adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
                    as_of=command.as_of,
                    requested_session_count=command.requested_session_count,
                    completion_grace=command.completion_grace,
                ),
            )
            for member in universe.members
        )

    @staticmethod
    def _identity(
        command: RunDailyFeaturePipelineCommand,
        prepared: tuple[PreparedPipelineMember, ...],
    ) -> DailyFeaturePipelineIdentity:
        resolved = tuple(
            entry.result.request.completed_through_session_date
            for entry in prepared
            if entry.result.request is not None
        )
        if len(set(resolved)) > 1:
            resolved = ()
        calendar = prepared[0].result
        return DailyFeaturePipelineIdentity(
            universe_snapshot_id=command.universe_snapshot_id,
            provider_code=command.provider_code,
            calendar_code=calendar.calendar_code,
            calendar_version=calendar.calendar_version,
            completed_session_date=resolved[0] if resolved else None,
            adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            horizon=command.horizon,
            requested_session_count=command.requested_session_count,
            as_of=command.as_of,
            completion_grace=command.completion_grace,
            pipeline_code=command.policy.pipeline_code,
            pipeline_version=command.policy.pipeline_version,
            feature_set_code=command.policy.feature_set_code,
            feature_set_version=command.policy.feature_set_version,
        )

    def _provider_preflight_reason(
        self,
        command: RunDailyFeaturePipelineCommand,
    ) -> str | None:
        if command.policy == DAILY_FEATURE_PIPELINE_POLICY_V2:
            if self.price_feature_service is None:
                return "FEATURE_POLICY_SERVICE_UNAVAILABLE"
        elif command.policy != DAILY_FEATURE_PIPELINE_POLICY_V1:
            return "FEATURE_POLICY_UNSUPPORTED"
        maximum = self.budget.maximum_rows_per_request
        if (
            command.provider_code != self.budget.provider_code
            or command.provider_code != TWELVE_DATA_SOURCE_CODE
        ):
            return "PROVIDER_CODE_UNSUPPORTED"
        if self.budget.provider_role is not DailyMarketDataProviderRole.PRIMARY_FEATURE_SOURCE:
            return "PROVIDER_ROLE_UNSUPPORTED"
        if not self.budget.enabled:
            return TwelveDataErrorCategory.PROVIDER_DISABLED.value
        if not self.budget.configured:
            return TwelveDataErrorCategory.CONFIGURATION_MISSING.value
        if maximum is None or command.requested_session_count > maximum:
            return "PROVIDER_CAPABILITY_UNSUPPORTED"
        return None

    def _executor(
        self,
        command: RunDailyFeaturePipelineCommand,
    ) -> SequentialDailyFeaturePipelineExecutor:
        return SequentialDailyFeaturePipelineExecutor(
            self.budget,
            self.ingestion_service,
            self.feature_service,
            self.clock,
            self.item_id_factory,
            self.transient_failure_limit,
            command.policy,
            self.price_feature_service,
        )

    def _store(self) -> DailyFeaturePipelineRunStore:
        return DailyFeaturePipelineRunStore(self.unit_of_work_factory, self.clock)
