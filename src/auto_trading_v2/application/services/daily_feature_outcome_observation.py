"""Read-only source consumption and immutable P4B.1 observation orchestration."""

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.feature_outcomes import (
    DailyFeatureOutcomeObservationExecutionOutcome,
    DailyFeatureOutcomeObservationExecutionResult,
    NewDailyFeatureOutcome,
    NewDailyFeatureOutcomeObservationRunWithItems,
    ObserveDailyFeatureScoringOutcomesCommand,
)
from auto_trading_v2.application.ports.id_factory import (
    DailyFeatureOutcomeIDFactory,
    DailyFeatureOutcomeObservationRunIDFactory,
    DailyFeatureOutcomeObservationRunItemIDFactory,
)
from auto_trading_v2.application.ports.market_calendar import UsEquityMarketCalendar
from auto_trading_v2.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from auto_trading_v2.application.services.daily_feature_outcome_builder import (
    build_daily_feature_outcome,
    future_sessions,
    validate_outcome_source,
)
from auto_trading_v2.application.services.daily_feature_outcome_persistence import (
    CanonicalOutcomeStoreDisposition,
    DailyFeatureOutcomeObservationRunStore,
    DailyFeatureOutcomeStore,
)
from auto_trading_v2.application.services.daily_feature_outcome_run_builder import (
    ObservationRunItemSource,
    build_observation_run,
)
from auto_trading_v2.application.services.daily_feature_outcome_types import (
    PreparedOutcomeItem,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    DailyFeatureOutcomeObservationRunItemOutcome,
    OutcomeObservationRunIdentity,
    OutcomeObservationValidationError,
    calculate_forward_outcome,
    daily_feature_outcome_observation_run_key,
    fixed_outcome_policy_values,
    observation_mode,
)
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineRunWithItems
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringItem,
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRun,
    DailyFeatureScoringRunStatus,
)
from auto_trading_v2.domain.market_calendar import MarketCalendarValidationError
from auto_trading_v2.ports.clock import Clock

_ELIGIBLE_RUNS = frozenset(
    {
        DailyFeatureScoringRunStatus.COMPLETED,
        DailyFeatureScoringRunStatus.COMPLETED_WITH_UNSCORABLE,
    }
)
_ELIGIBLE_ITEMS = frozenset(
    {
        DailyFeatureScoringItemOutcome.SCORED_READY,
        DailyFeatureScoringItemOutcome.SCORED_DEGRADED,
    }
)


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeObservationService:
    unit_of_work_factory: UnitOfWorkFactory
    calendar: UsEquityMarketCalendar
    clock: Clock
    outcome_id_factory: DailyFeatureOutcomeIDFactory
    run_id_factory: DailyFeatureOutcomeObservationRunIDFactory
    run_item_id_factory: DailyFeatureOutcomeObservationRunItemIDFactory

    def observe(
        self,
        command: ObserveDailyFeatureScoringOutcomesCommand,
    ) -> DailyFeatureOutcomeObservationExecutionResult:
        policy_code, policy_version = fixed_outcome_policy_values()
        identity = OutcomeObservationRunIdentity(
            command.daily_feature_scoring_run_id,
            policy_code,
            policy_version,
            command.observation_as_of,
            int(command.completion_grace.value.total_seconds()),
        )
        run_key = daily_feature_outcome_observation_run_key(identity)
        run_store = DailyFeatureOutcomeObservationRunStore(self.unit_of_work_factory)
        existing = run_store.existing(run_key)
        if existing is not None:
            return DailyFeatureOutcomeObservationExecutionResult(
                DailyFeatureOutcomeObservationExecutionOutcome.ALREADY_EXISTS,
                existing,
            )
        generated_at = self.clock.now_utc()
        prepared = self._prepare(command, generated_at)
        if isinstance(prepared, DailyFeatureOutcomeObservationExecutionResult):
            return prepared
        persisted = self._persist_outcomes(prepared)
        sources = tuple(
            ObservationRunItemSource(
                item.source_item.daily_feature_scoring_item_id,
                item.outcome,
                None if item.candidate is None else item.candidate.daily_feature_outcome_id,
                item.terminal_session_date,
            )
            for item in persisted
        )
        aggregate = build_observation_run(
            identity,
            run_key,
            sources,
            generated_at,
            self.run_id_factory,
            self.run_item_id_factory,
        )
        created, stored = run_store.persist(
            NewDailyFeatureOutcomeObservationRunWithItems(aggregate)
        )
        return DailyFeatureOutcomeObservationExecutionResult(
            DailyFeatureOutcomeObservationExecutionOutcome.CREATED
            if created
            else DailyFeatureOutcomeObservationExecutionOutcome.ALREADY_EXISTS,
            stored,
        )

    def _prepare(
        self,
        command: ObserveDailyFeatureScoringOutcomesCommand,
        generated_at: datetime,
    ) -> tuple[PreparedOutcomeItem, ...] | DailyFeatureOutcomeObservationExecutionResult:
        with self.unit_of_work_factory() as unit_of_work:
            scoring = unit_of_work.daily_feature_scoring_runs.get_run_with_items(
                command.daily_feature_scoring_run_id
            )
            if scoring is None:
                return _failure(
                    DailyFeatureOutcomeObservationExecutionOutcome.SOURCE_SCORING_RUN_NOT_FOUND,
                    "SOURCE_SCORING_RUN_NOT_FOUND",
                )
            if scoring.run.status not in _ELIGIBLE_RUNS or not self._calendar_supported():
                return _failure(
                    DailyFeatureOutcomeObservationExecutionOutcome.SOURCE_SCORING_RUN_NOT_ELIGIBLE,
                    "SOURCE_SCORING_RUN_NOT_ELIGIBLE",
                )
            pipeline = unit_of_work.daily_feature_pipeline_runs.get_run_with_items(
                scoring.run.identity.source_daily_feature_pipeline_run_id
            )
            return tuple(
                self._prepare_item(
                    unit_of_work,
                    scoring.run,
                    item,
                    pipeline,
                    command,
                    generated_at,
                )
                for item in scoring.items
            )

    def _prepare_item(
        self,
        unit_of_work: UnitOfWork,
        scoring_run: DailyFeatureScoringRun,
        scoring_item: DailyFeatureScoringItem,
        pipeline: DailyFeaturePipelineRunWithItems | None,
        command: ObserveDailyFeatureScoringOutcomesCommand,
        generated_at: datetime,
    ) -> PreparedOutcomeItem:
        if scoring_item.outcome not in _ELIGIBLE_ITEMS:
            return PreparedOutcomeItem(
                scoring_item,
                DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE,
            )
        snapshot = (
            None
            if scoring_item.feature_snapshot_id is None
            else unit_of_work.feature_snapshots.get_by_id(scoring_item.feature_snapshot_id)
        )
        source = validate_outcome_source(scoring_run, scoring_item, pipeline, snapshot)
        if source is None:
            return PreparedOutcomeItem(
                scoring_item,
                DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,
            )
        try:
            sessions = self.calendar.sessions(scoring_item.mic_code)
        except MarketCalendarValidationError:
            return PreparedOutcomeItem(
                scoring_item,
                DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,
            )
        selected = future_sessions(
            sessions,
            source.pipeline.run.identity.completed_session_date,
            source.pipeline.run.identity.horizon.value,
        )
        if selected is None:
            return PreparedOutcomeItem(
                scoring_item,
                DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,
            )
        if not selected:
            return PreparedOutcomeItem(
                scoring_item,
                DailyFeatureOutcomeObservationRunItemOutcome.CALENDAR_OUT_OF_COVERAGE,
            )
        terminal = selected[-1].session_date
        if command.observation_as_of < selected[-1].close_at + command.completion_grace.value:
            return PreparedOutcomeItem(
                scoring_item,
                DailyFeatureOutcomeObservationRunItemOutcome.NOT_MATURED,
                terminal_session_date=terminal,
            )
        expected = tuple(session.session_date for session in selected)
        bars = unit_of_work.daily_market_bars.list_latest_available_for_sessions(
            source.pipeline.run.identity.provider_code,
            scoring_item.symbol,
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
            expected,
            command.observation_as_of,
        )
        try:
            calculated = calculate_forward_outcome(
                source.reference_close,
                bars,
                expected,
                scoring_item.symbol,
                command.observation_as_of,
            )
        except OutcomeObservationValidationError as exc:
            outcome = (
                DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BARS_INCOMPLETE
                if exc.category == "FUTURE_BARS_INCOMPLETE"
                else DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BAR_CONTRACT_INVALID
            )
            return PreparedOutcomeItem(scoring_item, outcome, terminal_session_date=terminal)
        candidate = build_daily_feature_outcome(
            self.outcome_id_factory.new(),
            scoring_run,
            scoring_item,
            source,
            calculated,
            command.observation_as_of,
            observation_mode(scoring_run.generated_at, selected[0].open_at),
            generated_at,
        )
        return PreparedOutcomeItem(
            scoring_item,
            DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED,
            candidate,
            terminal,
        )

    def _persist_outcomes(
        self, items: tuple[PreparedOutcomeItem, ...]
    ) -> tuple[PreparedOutcomeItem, ...]:
        store = DailyFeatureOutcomeStore(self.unit_of_work_factory)
        resolved: list[PreparedOutcomeItem] = []
        for item in items:
            if item.candidate is None:
                resolved.append(item)
                continue
            result = store.persist(NewDailyFeatureOutcome(item.candidate))
            outcome = (
                DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED
                if result.disposition is CanonicalOutcomeStoreDisposition.CREATED
                else DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_ALREADY_EXISTS
            )
            resolved.append(
                PreparedOutcomeItem(
                    item.source_item,
                    outcome,
                    result.outcome,
                    item.terminal_session_date,
                )
            )
        return tuple(resolved)

    def _calendar_supported(self) -> bool:
        metadata = self.calendar.metadata
        return (
            metadata.calendar_code.value == CALENDAR_CODE
            and metadata.calendar_version.value == CALENDAR_VERSION
        )


def _failure(
    outcome: DailyFeatureOutcomeObservationExecutionOutcome,
    reason: str,
) -> DailyFeatureOutcomeObservationExecutionResult:
    return DailyFeatureOutcomeObservationExecutionResult(outcome, None, reason)
