"""Aggregate invariants for immutable P4B.2A datasets."""

from dataclasses import dataclass

from auto_trading_v2.domain.calibration_datasets.digest import (
    calibration_dataset_content_digest,
)
from auto_trading_v2.domain.calibration_datasets.errors import (
    ProbabilityCalibrationDatasetValidationError,
)
from auto_trading_v2.domain.calibration_datasets.models import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
    dataset_item_order_key,
)
from auto_trading_v2.domain.calibration_datasets.outcomes import (
    ProbabilityCalibrationDatasetStatus,
)
from auto_trading_v2.domain.feature_outcomes import OutcomeObservationMode
from auto_trading_v2.domain.outcome_labels import PositiveForwardCloseLabel


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDatasetWithItems:
    dataset: ProbabilityCalibrationDataset
    items: tuple[ProbabilityCalibrationDatasetItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, ProbabilityCalibrationDataset) or not isinstance(
            self.items, tuple
        ):
            _invalid("DATASET_AGGREGATE_TYPE_INVALID")
        if any(not isinstance(item, ProbabilityCalibrationDatasetItem) for item in self.items):
            _invalid("DATASET_AGGREGATE_ITEM_INVALID")
        expected_order = tuple(sorted(self.items, key=dataset_item_order_key))
        if self.items != expected_order:
            _invalid("DATASET_ITEM_ORDER_INVALID")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _invalid("DATASET_ITEM_ORDINAL_SEQUENCE_INVALID")
        if any(
            item.probability_calibration_dataset_id
            != self.dataset.probability_calibration_dataset_id
            for item in self.items
        ):
            _invalid("DATASET_ITEM_PARENT_INVALID")
        source_sets = (
            {item.source_daily_feature_scoring_item_id for item in self.items},
            {item.source_daily_feature_outcome_id for item in self.items},
            {item.source_daily_feature_outcome_label_id for item in self.items},
        )
        if any(len(values) != len(self.items) for values in source_sets):
            _invalid("DATASET_ITEM_SOURCE_DUPLICATE")
        if any(
            item.horizon != self.dataset.identity.horizon
            or item.source_outcome_latest_input_available_at > self.dataset.identity.dataset_as_of
            or item.source_outcome_recorded_at > self.dataset.identity.dataset_as_of
            for item in self.items
        ):
            _invalid("DATASET_ITEM_POINT_IN_TIME_INVALID")
        self._validate_summary()
        if self.dataset.content_digest != calibration_dataset_content_digest(
            self.dataset, self.items
        ):
            _invalid("DATASET_CONTENT_DIGEST_MISMATCH")

    def _validate_summary(self) -> None:
        positive = sum(
            item.label_value is PositiveForwardCloseLabel.POSITIVE for item in self.items
        )
        prospective = sum(
            item.observation_mode is OutcomeObservationMode.PROSPECTIVE for item in self.items
        )
        sessions = {item.source_session_date for item in self.items}
        ordered_sessions = sorted(sessions, key=lambda value: value.value)
        expected = (
            len(self.items),
            positive,
            len(self.items) - positive,
            prospective,
            len(self.items) - prospective,
            len(sessions),
            None if not ordered_sessions else ordered_sessions[0],
            None if not ordered_sessions else ordered_sessions[-1],
            (
                ProbabilityCalibrationDatasetStatus.EMPTY
                if not self.items
                else ProbabilityCalibrationDatasetStatus.READY
            ),
        )
        actual = (
            self.dataset.total_count,
            self.dataset.positive_count,
            self.dataset.not_positive_count,
            self.dataset.prospective_count,
            self.dataset.retrospective_replay_count,
            self.dataset.unique_source_session_count,
            self.dataset.earliest_source_session_date,
            self.dataset.latest_source_session_date,
            self.dataset.status,
        )
        if actual != expected:
            _invalid("DATASET_SUMMARY_MISMATCH")


def _invalid(category: str) -> None:
    raise ProbabilityCalibrationDatasetValidationError(category)
