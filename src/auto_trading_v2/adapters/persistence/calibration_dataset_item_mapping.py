"""Safe row mapping for immutable P4B.2A dataset items."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.calibration_datasets import ProbabilityCalibrationDatasetItem
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


def map_probability_calibration_dataset_item(
    row: Mapping[Any, Any],
) -> ProbabilityCalibrationDatasetItem:
    try:
        return ProbabilityCalibrationDatasetItem(
            probability_calibration_dataset_item_id=ProbabilityCalibrationDatasetItemID(
                _uuid(row["probability_calibration_dataset_item_id"])
            ),
            probability_calibration_dataset_id=ProbabilityCalibrationDatasetID(
                _uuid(row["probability_calibration_dataset_id"])
            ),
            ordinal=_integer(row["ordinal"]),
            source_daily_feature_outcome_label_id=DailyFeatureOutcomeLabelID(
                _uuid(row["source_daily_feature_outcome_label_id"])
            ),
            source_daily_feature_outcome_id=DailyFeatureOutcomeID(
                _uuid(row["source_daily_feature_outcome_id"])
            ),
            source_daily_feature_scoring_run_id=DailyFeatureScoringRunID(
                _uuid(row["source_daily_feature_scoring_run_id"])
            ),
            source_daily_feature_scoring_item_id=DailyFeatureScoringItemID(
                _uuid(row["source_daily_feature_scoring_item_id"])
            ),
            source_daily_feature_pipeline_run_id=DailyFeaturePipelineRunID(
                _uuid(row["source_daily_feature_pipeline_run_id"])
            ),
            source_daily_feature_pipeline_item_id=DailyFeaturePipelineItemID(
                _uuid(row["source_daily_feature_pipeline_item_id"])
            ),
            feature_snapshot_id=FeatureSnapshotID(_uuid(row["feature_snapshot_id"])),
            source_outcome_key=_string(row["source_outcome_key"]),
            source_outcome_content_digest=_string(row["source_outcome_content_digest"]),
            symbol=Symbol(_string(row["symbol"])),
            mic_code=_string(row["mic_code"]),
            horizon=TradingDayHorizon(_integer(row["horizon_trading_days"])),
            source_session_date=SessionDate(_date(row["source_session_date"])),
            terminal_session_date=SessionDate(_date(row["terminal_session_date"])),
            observation_mode=OutcomeObservationMode(_string(row["observation_mode"])),
            source_quality_status=FeatureQualityStatus(_string(row["source_quality_status"])),
            overall_relative_score=RelativeScore(_decimal(row["overall_relative_score"])),
            source_rank=_integer(row["source_rank"]),
            label_value=PositiveForwardCloseLabel(_string(row["label_value"])),
            source_path_revision_digest=_string(row["source_path_revision_digest"]),
            source_outcome_latest_input_available_at=_datetime(
                row["source_outcome_latest_input_available_at"]
            ),
            source_outcome_recorded_at=_datetime(row["source_outcome_recorded_at"]),
            generated_at=_datetime(row["generated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("probability_calibration_dataset_item") from None


def new_probability_calibration_dataset_item_values(
    value: ProbabilityCalibrationDatasetItem,
) -> dict[str, object]:
    return {
        "probability_calibration_dataset_item_id": (
            value.probability_calibration_dataset_item_id.value
        ),
        "probability_calibration_dataset_id": value.probability_calibration_dataset_id.value,
        "ordinal": value.ordinal,
        "source_daily_feature_outcome_label_id": value.source_daily_feature_outcome_label_id.value,
        "source_daily_feature_outcome_id": value.source_daily_feature_outcome_id.value,
        "source_daily_feature_scoring_run_id": value.source_daily_feature_scoring_run_id.value,
        "source_daily_feature_scoring_item_id": value.source_daily_feature_scoring_item_id.value,
        "source_daily_feature_pipeline_run_id": value.source_daily_feature_pipeline_run_id.value,
        "source_daily_feature_pipeline_item_id": value.source_daily_feature_pipeline_item_id.value,
        "feature_snapshot_id": value.feature_snapshot_id.value,
        "source_outcome_key": value.source_outcome_key,
        "source_outcome_content_digest": value.source_outcome_content_digest,
        "symbol": value.symbol.value,
        "mic_code": value.mic_code,
        "horizon_trading_days": value.horizon.value,
        "source_session_date": value.source_session_date.value,
        "terminal_session_date": value.terminal_session_date.value,
        "observation_mode": value.observation_mode.value,
        "source_quality_status": value.source_quality_status.value,
        "overall_relative_score": value.overall_relative_score.value,
        "source_rank": value.source_rank,
        "label_value": value.label_value.value,
        "source_path_revision_digest": value.source_path_revision_digest,
        "source_outcome_latest_input_available_at": value.source_outcome_latest_input_available_at,
        "source_outcome_recorded_at": value.source_outcome_recorded_at,
        "generated_at": value.generated_at,
    }


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _date(value: object) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError
    return value


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
