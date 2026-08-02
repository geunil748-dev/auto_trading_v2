"""Create deterministic immutable positive-close labels from P4B.1 outcomes."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.outcome_labels import (
    CreateDailyFeatureOutcomeLabelCommand,
    DailyFeatureOutcomeLabelCreationOutcome,
    DailyFeatureOutcomeLabelCreationResult,
    NewDailyFeatureOutcomeLabel,
)
from auto_trading_v2.application.outcome_label_errors import (
    DailyFeatureOutcomeLabelSourceNotFoundError,
)
from auto_trading_v2.application.ports.id_factory import DailyFeatureOutcomeLabelIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_feature_outcome_label_persistence import (
    CanonicalLabelStoreDisposition,
    DailyFeatureOutcomeLabelStore,
)
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabel,
    DailyFeatureOutcomeLabelIdentity,
    fixed_label_policy_values,
    outcome_label_content_digest,
    outcome_label_key,
    positive_forward_close_label,
    validate_label_source,
)
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeLabelCreationService:
    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    label_id_factory: DailyFeatureOutcomeLabelIDFactory

    def create(
        self, command: CreateDailyFeatureOutcomeLabelCommand
    ) -> DailyFeatureOutcomeLabelCreationResult:
        policy_code, policy_version = fixed_label_policy_values()
        identity = DailyFeatureOutcomeLabelIdentity(
            command.source_daily_feature_outcome_id,
            policy_code,
            policy_version,
        )
        key = outcome_label_key(identity)
        store = DailyFeatureOutcomeLabelStore(self.unit_of_work_factory)
        existing = store.existing(key)
        if existing is not None:
            return DailyFeatureOutcomeLabelCreationResult(
                DailyFeatureOutcomeLabelCreationOutcome.ALREADY_EXISTS,
                existing,
            )
        with self.unit_of_work_factory() as unit_of_work:
            source = unit_of_work.daily_feature_outcomes.get_by_id(
                command.source_daily_feature_outcome_id
            )
        if source is None:
            raise DailyFeatureOutcomeLabelSourceNotFoundError()
        source = validate_label_source(source)
        label_value = positive_forward_close_label(source.forward_close_return)
        generated_at = self.clock.now_utc()
        label = DailyFeatureOutcomeLabel(
            daily_feature_outcome_label_id=self.label_id_factory.new(),
            label_key=key,
            content_digest=outcome_label_content_digest(
                source,
                policy_code,
                policy_version,
                label_value,
            ),
            source_daily_feature_outcome_id=source.daily_feature_outcome_id,
            source_daily_feature_scoring_run_id=source.source_daily_feature_scoring_run_id,
            source_daily_feature_scoring_item_id=source.source_daily_feature_scoring_item_id,
            source_daily_feature_pipeline_run_id=source.source_daily_feature_pipeline_run_id,
            source_daily_feature_pipeline_item_id=source.source_daily_feature_pipeline_item_id,
            feature_snapshot_id=source.feature_snapshot_id,
            symbol=source.symbol,
            mic_code=source.mic_code,
            horizon=source.horizon,
            source_session_date=source.source_session_date,
            terminal_session_date=source.terminal_session_date,
            observation_mode=source.observation_mode,
            source_path_revision_digest=source.path_revision_digest,
            label_policy_code=policy_code,
            label_policy_version=policy_version,
            label_value=label_value,
            source_latest_input_available_at=source.latest_input_available_at,
            generated_at=generated_at,
            recorded_at=generated_at,
        )
        stored = store.persist(NewDailyFeatureOutcomeLabel(label))
        outcome = (
            DailyFeatureOutcomeLabelCreationOutcome.CREATED
            if stored.disposition is CanonicalLabelStoreDisposition.CREATED
            else DailyFeatureOutcomeLabelCreationOutcome.ALREADY_EXISTS
        )
        return DailyFeatureOutcomeLabelCreationResult(outcome, stored.label)
