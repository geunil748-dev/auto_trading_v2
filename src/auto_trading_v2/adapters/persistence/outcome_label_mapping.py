"""Safe row mapping for immutable P4B.2A outcome labels."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.outcome_labels import NewDailyFeatureOutcomeLabel
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import OutcomeObservationMode
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabel,
    OutcomeLabelPolicyCode,
    OutcomeLabelPolicyVersion,
    PositiveForwardCloseLabel,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
)


def map_daily_feature_outcome_label(row: Mapping[Any, Any]) -> DailyFeatureOutcomeLabel:
    try:
        return DailyFeatureOutcomeLabel(
            daily_feature_outcome_label_id=DailyFeatureOutcomeLabelID(
                _uuid(row["daily_feature_outcome_label_id"])
            ),
            label_key=_string(row["label_key"]),
            content_digest=_string(row["content_digest"]),
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
            symbol=Symbol(_string(row["symbol"])),
            mic_code=_string(row["mic_code"]),
            horizon=TradingDayHorizon(_integer(row["horizon_trading_days"])),
            source_session_date=SessionDate(_date(row["source_session_date"])),
            terminal_session_date=SessionDate(_date(row["terminal_session_date"])),
            observation_mode=OutcomeObservationMode(_string(row["observation_mode"])),
            source_path_revision_digest=_string(row["source_path_revision_digest"]),
            label_policy_code=OutcomeLabelPolicyCode(_string(row["label_policy_code"])),
            label_policy_version=OutcomeLabelPolicyVersion(_string(row["label_policy_version"])),
            label_value=PositiveForwardCloseLabel(_string(row["label_value"])),
            source_latest_input_available_at=_datetime(row["source_latest_input_available_at"]),
            generated_at=_datetime(row["generated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("daily_feature_outcome_label") from None


def new_daily_feature_outcome_label_values(
    candidate: NewDailyFeatureOutcomeLabel,
) -> dict[str, object]:
    value = candidate.label
    return {
        "daily_feature_outcome_label_id": value.daily_feature_outcome_label_id.value,
        "label_key": value.label_key,
        "content_digest": value.content_digest,
        "source_daily_feature_outcome_id": value.source_daily_feature_outcome_id.value,
        "source_daily_feature_scoring_run_id": value.source_daily_feature_scoring_run_id.value,
        "source_daily_feature_scoring_item_id": value.source_daily_feature_scoring_item_id.value,
        "source_daily_feature_pipeline_run_id": value.source_daily_feature_pipeline_run_id.value,
        "source_daily_feature_pipeline_item_id": value.source_daily_feature_pipeline_item_id.value,
        "feature_snapshot_id": value.feature_snapshot_id.value,
        "symbol": value.symbol.value,
        "mic_code": value.mic_code,
        "horizon_trading_days": value.horizon.value,
        "source_session_date": value.source_session_date.value,
        "terminal_session_date": value.terminal_session_date.value,
        "observation_mode": value.observation_mode.value,
        "source_path_revision_digest": value.source_path_revision_digest,
        "label_policy_code": value.label_policy_code.value,
        "label_policy_version": value.label_policy_version.value,
        "label_value": value.label_value.value,
        "source_latest_input_available_at": value.source_latest_input_available_at,
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


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
