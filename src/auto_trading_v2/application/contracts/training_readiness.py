"""Explicit commands and read-only lineage rows for training-readiness audits."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from auto_trading_v2.domain.primitives import (
    DailyFeatureScoringItemID,
    ProbabilityCalibrationDatasetID,
    Symbol,
)


@dataclass(frozen=True, slots=True)
class RunTrainingReadinessAuditCommand:
    probability_calibration_dataset_id: ProbabilityCalibrationDatasetID

    def __post_init__(self) -> None:
        if not isinstance(self.probability_calibration_dataset_id, ProbabilityCalibrationDatasetID):
            raise TypeError("probability_calibration_dataset_id is invalid")


@dataclass(frozen=True, slots=True)
class RunTrainingReadinessAuditBatchCommand:
    probability_calibration_dataset_ids: tuple[ProbabilityCalibrationDatasetID, ...]

    def __post_init__(self) -> None:
        identifiers = self.probability_calibration_dataset_ids
        if (
            not isinstance(identifiers, tuple)
            or not identifiers
            or any(not isinstance(value, ProbabilityCalibrationDatasetID) for value in identifiers)
            or len(identifiers) != len(set(identifiers))
        ):
            raise ValueError("explicit unique dataset IDs are required")


@dataclass(frozen=True, slots=True)
class TrainingReadinessLineageRecord:
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    symbol: Symbol
    mic_code: str
    source_session_date: date | None
    provider_code: str
    calendar_code: str
    calendar_version: str
    scoring_policy_code: str
    scoring_policy_version: str
    ranking_policy_code: str
    ranking_policy_version: str
    scoring_outcome: str
    source_quality_status: str | None
    pipeline_outcome: str
    feature_set_code: str | None
    feature_set_version: str | None
    feature_quality_status: str | None
    quality_reason_codes: tuple[str, ...]
    feature_values: Mapping[str, object] | None
    overall_relative_score: Decimal | None
    source_rank: int | None
    has_any_outcome: bool
    has_as_of_outcome: bool
    has_provider_outcome: bool
    has_calendar_outcome: bool
    has_policy_outcome: bool
    has_any_label: bool
    has_matching_label: bool
