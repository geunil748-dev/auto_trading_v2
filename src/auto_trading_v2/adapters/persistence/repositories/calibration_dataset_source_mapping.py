"""Persistence row mapping for P4B.2A calibration dataset sources."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import ForwardReturn, OutcomeObservationMode
from auto_trading_v2.domain.feature_scoring import RelativeScore
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
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


def map_calibration_dataset_source(
    row: Mapping[Any, Any],
) -> CalibrationDatasetSourceRecord:
    try:
        return CalibrationDatasetSourceRecord(
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
            source_daily_feature_outcome_id=DailyFeatureOutcomeID(
                _uuid(row["source_daily_feature_outcome_id"])
            ),
            source_outcome_key=_string(row["source_outcome_key"]),
            source_outcome_content_digest=_string(row["source_outcome_content_digest"]),
            source_path_revision_digest=_string(row["source_path_revision_digest"]),
            symbol=Symbol(_string(row["symbol"])),
            mic_code=_string(row["mic_code"]),
            horizon=TradingDayHorizon(_integer(row["horizon_trading_days"])),
            source_session_date=SessionDate(_date(row["source_session_date"])),
            terminal_session_date=SessionDate(_date(row["terminal_session_date"])),
            source_scoring_generated_at=_datetime(row["source_scoring_generated_at"]),
            source_scoring_item_recorded_at=_datetime(row["source_scoring_item_recorded_at"]),
            outcome_latest_input_available_at=_datetime(row["outcome_latest_input_available_at"]),
            outcome_recorded_at=_datetime(row["outcome_recorded_at"]),
            observation_mode=OutcomeObservationMode(_string(row["observation_mode"])),
            source_quality_status=FeatureQualityStatus(_string(row["source_quality_status"])),
            overall_relative_score=RelativeScore(_decimal(row["overall_relative_score"])),
            rank=_integer(row["source_rank"]),
            forward_close_return=ForwardReturn(_decimal(row["forward_close_return"])),
            provider_code=_string(row["provider_code"]),
            calendar_code=_string(row["calendar_code"]),
            calendar_version=_string(row["calendar_version"]),
            outcome_policy_code=_string(row["outcome_policy_code"]),
            outcome_policy_version=_string(row["outcome_policy_version"]),
            scoring_policy_code=_string(row["scoring_policy_code"]),
            scoring_policy_version=_string(row["scoring_policy_version"]),
            ranking_policy_code=_string(row["ranking_policy_code"]),
            ranking_policy_version=_string(row["ranking_policy_version"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("probability_calibration_dataset_source") from None


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
