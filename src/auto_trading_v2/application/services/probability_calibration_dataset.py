"""Create immutable READY-score/positive-close dataset snapshots."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.calibration_datasets import (
    CreateProbabilityCalibrationDatasetCommand,
    NewProbabilityCalibrationDatasetWithItems,
    ProbabilityCalibrationDatasetCreationOutcome,
    ProbabilityCalibrationDatasetCreationResult,
)
from auto_trading_v2.application.contracts.outcome_labels import (
    CreateDailyFeatureOutcomeLabelCommand,
)
from auto_trading_v2.application.ports.calibration_datasets import (
    ProbabilityCalibrationDatasetSourceReader,
)
from auto_trading_v2.application.ports.id_factory import (
    ProbabilityCalibrationDatasetIDFactory,
    ProbabilityCalibrationDatasetItemIDFactory,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_feature_outcome_label import (
    DailyFeatureOutcomeLabelCreationService,
)
from auto_trading_v2.application.services.probability_calibration_dataset_builder import (
    build_calibration_dataset,
    validate_and_order_sources,
)
from auto_trading_v2.application.services.probability_calibration_dataset_persistence import (
    CanonicalDatasetStoreDisposition,
    ProbabilityCalibrationDatasetStore,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetIdentity,
    ProbabilityCalibrationDatasetValidationError,
    calibration_dataset_key,
    fixed_dataset_policy_values,
)
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    SOURCE_PROVIDER_CODE,
    fixed_outcome_policy_values,
)
from auto_trading_v2.domain.feature_scoring import fixed_policy_values
from auto_trading_v2.domain.market_calendar import ExchangeCalendarCode, ExchangeCalendarVersion
from auto_trading_v2.domain.outcome_labels import fixed_label_policy_values
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDatasetCreationService:
    unit_of_work_factory: UnitOfWorkFactory
    source_reader: ProbabilityCalibrationDatasetSourceReader
    label_creation_service: DailyFeatureOutcomeLabelCreationService
    clock: Clock
    dataset_id_factory: ProbabilityCalibrationDatasetIDFactory
    item_id_factory: ProbabilityCalibrationDatasetItemIDFactory

    def create(
        self, command: CreateProbabilityCalibrationDatasetCommand
    ) -> ProbabilityCalibrationDatasetCreationResult:
        generated_at = self.clock.now_utc()
        if command.dataset_as_of > generated_at:
            raise ProbabilityCalibrationDatasetValidationError("DATASET_AS_OF_IN_FUTURE")
        dataset_policy_code, dataset_policy_version = fixed_dataset_policy_values()
        label_policy_code, label_policy_version = fixed_label_policy_values()
        outcome_policy_code, outcome_policy_version = fixed_outcome_policy_values()
        (
            scoring_policy_code,
            scoring_policy_version,
            ranking_policy_code,
            ranking_policy_version,
        ) = fixed_policy_values()
        identity = ProbabilityCalibrationDatasetIdentity(
            dataset_policy_code=dataset_policy_code,
            dataset_policy_version=dataset_policy_version,
            label_policy_code=label_policy_code,
            label_policy_version=label_policy_version,
            outcome_policy_code=outcome_policy_code,
            outcome_policy_version=outcome_policy_version,
            scoring_policy_code=scoring_policy_code,
            scoring_policy_version=scoring_policy_version,
            ranking_policy_code=ranking_policy_code,
            ranking_policy_version=ranking_policy_version,
            provider_code=SOURCE_PROVIDER_CODE,
            calendar_code=ExchangeCalendarCode(CALENDAR_CODE),
            calendar_version=ExchangeCalendarVersion(CALENDAR_VERSION),
            horizon=command.horizon,
            dataset_as_of=command.dataset_as_of,
        )
        store = ProbabilityCalibrationDatasetStore(self.unit_of_work_factory)
        existing = store.existing(calibration_dataset_key(identity))
        if existing is not None:
            return ProbabilityCalibrationDatasetCreationResult(
                ProbabilityCalibrationDatasetCreationOutcome.ALREADY_EXISTS,
                existing,
            )
        sources = validate_and_order_sources(
            self.source_reader.list_eligible_sources(
                command.horizon,
                command.dataset_as_of,
                dataset_policy_code,
                dataset_policy_version,
            ),
            identity,
        )
        labels = tuple(
            self.label_creation_service.create(
                CreateDailyFeatureOutcomeLabelCommand(source.source_daily_feature_outcome_id)
            ).label
            for source in sources
        )
        aggregate = build_calibration_dataset(
            identity,
            sources,
            labels,
            generated_at,
            self.dataset_id_factory,
            self.item_id_factory,
        )
        stored = store.persist(NewProbabilityCalibrationDatasetWithItems(aggregate))
        outcome = (
            ProbabilityCalibrationDatasetCreationOutcome.CREATED
            if stored.disposition is CanonicalDatasetStoreDisposition.CREATED
            else ProbabilityCalibrationDatasetCreationOutcome.ALREADY_EXISTS
        )
        return ProbabilityCalibrationDatasetCreationResult(outcome, stored.aggregate)
