"""Commands, source records, and inserts for P4B.2A datasets."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.calibration_datasets import (
    DATASET_POLICY_CODE,
    DATASET_POLICY_VERSION,
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    ForwardReturn,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.feature_scoring import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
    RelativeScore,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.outcome_labels import LABEL_POLICY_CODE, LABEL_POLICY_VERSION
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc


@dataclass(frozen=True, slots=True)
class CreateProbabilityCalibrationDatasetCommand:
    horizon: TradingDayHorizon
    dataset_as_of: datetime
    dataset_policy_code: str = DATASET_POLICY_CODE
    dataset_policy_version: str = DATASET_POLICY_VERSION
    label_policy_code: str = LABEL_POLICY_CODE
    label_policy_version: str = LABEL_POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, TradingDayHorizon):
            raise ValueError("horizon is invalid")
        expected = (
            DATASET_POLICY_CODE,
            DATASET_POLICY_VERSION,
            LABEL_POLICY_CODE,
            LABEL_POLICY_VERSION,
        )
        actual = (
            self.dataset_policy_code,
            self.dataset_policy_version,
            self.label_policy_code,
            self.label_policy_version,
        )
        if actual != expected:
            raise ValueError("P4B.2A dataset policy is unsupported")
        try:
            normalized = normalize_utc(self.dataset_as_of)
        except (TypeError, ValidationError):
            raise ValueError("dataset_as_of must be timezone-aware") from None
        object.__setattr__(self, "dataset_as_of", normalized)


@dataclass(frozen=True, slots=True)
class CalibrationDatasetSourceRecord:
    source_daily_feature_scoring_run_id: DailyFeatureScoringRunID
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    source_daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    source_daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    feature_snapshot_id: FeatureSnapshotID
    source_daily_feature_outcome_id: DailyFeatureOutcomeID
    source_outcome_key: str
    source_outcome_content_digest: str
    source_path_revision_digest: str
    symbol: Symbol
    mic_code: str
    horizon: TradingDayHorizon
    source_session_date: SessionDate
    terminal_session_date: SessionDate
    source_scoring_generated_at: datetime
    source_scoring_item_recorded_at: datetime
    outcome_latest_input_available_at: datetime
    outcome_recorded_at: datetime
    observation_mode: OutcomeObservationMode
    source_quality_status: FeatureQualityStatus
    overall_relative_score: RelativeScore
    rank: int
    forward_close_return: ForwardReturn
    provider_code: str
    calendar_code: str
    calendar_version: str
    outcome_policy_code: str = OUTCOME_POLICY_CODE
    outcome_policy_version: str = OUTCOME_POLICY_VERSION
    scoring_policy_code: str = SCORING_POLICY_CODE
    scoring_policy_version: str = SCORING_POLICY_VERSION
    ranking_policy_code: str = RANKING_POLICY_CODE
    ranking_policy_version: str = RANKING_POLICY_VERSION


@dataclass(frozen=True, slots=True)
class NewProbabilityCalibrationDatasetWithItems:
    aggregate: ProbabilityCalibrationDatasetWithItems

    def __post_init__(self) -> None:
        if not isinstance(self.aggregate, ProbabilityCalibrationDatasetWithItems):
            raise TypeError("aggregate is invalid")

    def stored(self, recorded_at: datetime) -> ProbabilityCalibrationDatasetWithItems:
        dataset_values = {
            name: getattr(self.aggregate.dataset, name)
            for name in self.aggregate.dataset.__dataclass_fields__
            if name != "recorded_at"
        }
        dataset = ProbabilityCalibrationDataset(**dataset_values, recorded_at=recorded_at)
        items = tuple(_stored_item(item, recorded_at) for item in self.aggregate.items)
        return ProbabilityCalibrationDatasetWithItems(dataset, items)


class ProbabilityCalibrationDatasetCreationOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDatasetCreationResult:
    outcome: ProbabilityCalibrationDatasetCreationOutcome
    dataset: ProbabilityCalibrationDatasetWithItems


def _stored_item(
    item: ProbabilityCalibrationDatasetItem,
    recorded_at: datetime,
) -> ProbabilityCalibrationDatasetItem:
    values = {
        name: getattr(item, name) for name in item.__dataclass_fields__ if name != "recorded_at"
    }
    return ProbabilityCalibrationDatasetItem(**values, recorded_at=recorded_at)
