"""Immutable P4B.2A calibration dataset records."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from auto_trading_v2.domain.calibration_datasets.errors import (
    ProbabilityCalibrationDatasetValidationError,
)
from auto_trading_v2.domain.calibration_datasets.identity import (
    ProbabilityCalibrationDatasetIdentity,
    calibration_dataset_key,
)
from auto_trading_v2.domain.calibration_datasets.outcomes import (
    ProbabilityCalibrationDatasetStatus,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import OutcomeObservationMode
from auto_trading_v2.domain.feature_scoring import RelativeScore
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.outcome_labels import PositiveForwardCloseLabel
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    ProbabilityCalibrationDatasetID,
    ProbabilityCalibrationDatasetItemID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_DATASET_KEY = re.compile(r"^probability-calibration-dataset:v1:[0-9a-f]{64}$")
_OUTCOME_KEY = re.compile(r"^daily-feature-outcome:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDatasetItem:
    probability_calibration_dataset_item_id: ProbabilityCalibrationDatasetItemID
    probability_calibration_dataset_id: ProbabilityCalibrationDatasetID
    ordinal: int
    source_daily_feature_outcome_label_id: DailyFeatureOutcomeLabelID
    source_daily_feature_outcome_id: DailyFeatureOutcomeID
    source_daily_feature_scoring_run_id: DailyFeatureScoringRunID
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    source_daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    source_daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    feature_snapshot_id: FeatureSnapshotID
    source_outcome_key: str
    source_outcome_content_digest: str
    symbol: Symbol
    mic_code: str
    horizon: TradingDayHorizon
    source_session_date: SessionDate
    terminal_session_date: SessionDate
    observation_mode: OutcomeObservationMode
    source_quality_status: FeatureQualityStatus
    overall_relative_score: RelativeScore
    source_rank: int
    label_value: PositiveForwardCloseLabel
    source_path_revision_digest: str
    source_outcome_latest_input_available_at: datetime = field(repr=False)
    source_outcome_recorded_at: datetime = field(repr=False)
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        self._validate_types()
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 1:
            _invalid("DATASET_ITEM_ORDINAL_INVALID")
        if (
            isinstance(self.source_rank, bool)
            or not isinstance(self.source_rank, int)
            or not 1 <= self.source_rank <= 100
        ):
            _invalid("DATASET_ITEM_RANK_INVALID")
        if (
            self.mic_code not in _MICS
            or self.source_quality_status is not FeatureQualityStatus.READY
            or self.source_session_date.value >= self.terminal_session_date.value
        ):
            _invalid("DATASET_ITEM_SOURCE_INVALID")
        if not _OUTCOME_KEY.fullmatch(self.source_outcome_key):
            _invalid("DATASET_ITEM_OUTCOME_KEY_INVALID")
        if any(
            not _DIGEST.fullmatch(value)
            for value in (self.source_outcome_content_digest, self.source_path_revision_digest)
        ):
            _invalid("DATASET_ITEM_DIGEST_INVALID")
        latest = _timestamp(
            self.source_outcome_latest_input_available_at, "DATASET_ITEM_AVAILABLE_INVALID"
        )
        source_recorded = _timestamp(
            self.source_outcome_recorded_at, "DATASET_ITEM_SOURCE_RECORDED_INVALID"
        )
        generated = _timestamp(self.generated_at, "DATASET_ITEM_GENERATED_INVALID")
        recorded = _timestamp(self.recorded_at, "DATASET_ITEM_RECORDED_INVALID")
        if not latest <= generated or not source_recorded <= generated or not generated <= recorded:
            _invalid("DATASET_ITEM_TIME_ORDER_INVALID")
        object.__setattr__(self, "source_outcome_latest_input_available_at", latest)
        object.__setattr__(self, "source_outcome_recorded_at", source_recorded)
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    def _validate_types(self) -> None:
        expected = (
            (self.probability_calibration_dataset_item_id, ProbabilityCalibrationDatasetItemID),
            (self.probability_calibration_dataset_id, ProbabilityCalibrationDatasetID),
            (self.source_daily_feature_outcome_label_id, DailyFeatureOutcomeLabelID),
            (self.source_daily_feature_outcome_id, DailyFeatureOutcomeID),
            (self.source_daily_feature_scoring_run_id, DailyFeatureScoringRunID),
            (self.source_daily_feature_scoring_item_id, DailyFeatureScoringItemID),
            (self.source_daily_feature_pipeline_run_id, DailyFeaturePipelineRunID),
            (self.source_daily_feature_pipeline_item_id, DailyFeaturePipelineItemID),
            (self.feature_snapshot_id, FeatureSnapshotID),
            (self.symbol, Symbol),
            (self.horizon, TradingDayHorizon),
            (self.source_session_date, SessionDate),
            (self.terminal_session_date, SessionDate),
            (self.observation_mode, OutcomeObservationMode),
            (self.source_quality_status, FeatureQualityStatus),
            (self.overall_relative_score, RelativeScore),
            (self.label_value, PositiveForwardCloseLabel),
        )
        if any(not isinstance(value, kind) for value, kind in expected):
            _invalid("DATASET_ITEM_TYPE_INVALID")


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDataset:
    probability_calibration_dataset_id: ProbabilityCalibrationDatasetID
    dataset_key: str
    content_digest: str
    identity: ProbabilityCalibrationDatasetIdentity = field(repr=False)
    status: ProbabilityCalibrationDatasetStatus
    total_count: int
    positive_count: int
    not_positive_count: int
    prospective_count: int
    retrospective_replay_count: int
    unique_source_session_count: int
    earliest_source_session_date: SessionDate | None
    latest_source_session_date: SessionDate | None
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.probability_calibration_dataset_id, ProbabilityCalibrationDatasetID):
            _invalid("DATASET_ID_INVALID")
        if not _DATASET_KEY.fullmatch(
            self.dataset_key
        ) or self.dataset_key != calibration_dataset_key(self.identity):
            _invalid("DATASET_KEY_INVALID")
        if not _DIGEST.fullmatch(self.content_digest):
            _invalid("DATASET_CONTENT_DIGEST_INVALID")
        if not isinstance(self.status, ProbabilityCalibrationDatasetStatus):
            _invalid("DATASET_STATUS_INVALID")
        self._validate_counts()
        generated = _timestamp(self.generated_at, "DATASET_GENERATED_INVALID")
        recorded = _timestamp(self.recorded_at, "DATASET_RECORDED_INVALID")
        if not self.identity.dataset_as_of <= generated <= recorded:
            _invalid("DATASET_TIME_ORDER_INVALID")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    def _validate_counts(self) -> None:
        counts = (
            self.total_count,
            self.positive_count,
            self.not_positive_count,
            self.prospective_count,
            self.retrospective_replay_count,
            self.unique_source_session_count,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts
        ):
            _invalid("DATASET_COUNT_INVALID")
        if self.total_count != self.positive_count + self.not_positive_count:
            _invalid("DATASET_LABEL_COUNT_INVALID")
        if self.total_count != self.prospective_count + self.retrospective_replay_count:
            _invalid("DATASET_MODE_COUNT_INVALID")
        dates = (self.earliest_source_session_date, self.latest_source_session_date)
        if self.status is ProbabilityCalibrationDatasetStatus.EMPTY:
            if any(counts) or dates != (None, None):
                _invalid("DATASET_EMPTY_SHAPE_INVALID")
        elif self.total_count < 1 or self.unique_source_session_count < 1 or None in dates:
            _invalid("DATASET_READY_SHAPE_INVALID")
        elif dates[0].value > dates[1].value:  # type: ignore[union-attr]
            _invalid("DATASET_SESSION_RANGE_INVALID")


def dataset_item_order_key(item: ProbabilityCalibrationDatasetItem) -> tuple[object, ...]:
    return (
        item.source_session_date.value,
        item.source_daily_feature_scoring_run_id.serialize(),
        item.source_rank,
        item.mic_code,
        item.symbol.serialize(),
        item.source_daily_feature_outcome_id.serialize(),
    )


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        raise ProbabilityCalibrationDatasetValidationError(category) from None


def _invalid(category: str) -> None:
    raise ProbabilityCalibrationDatasetValidationError(category)
