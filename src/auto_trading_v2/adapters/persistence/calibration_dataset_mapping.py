"""Safe row mapping for immutable P4B.2A dataset headers."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.calibration_datasets import (
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.calibration_datasets import (
    CalibrationDatasetPolicyCode,
    CalibrationDatasetPolicyVersion,
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetIdentity,
    ProbabilityCalibrationDatasetStatus,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
)
from auto_trading_v2.domain.feature_scoring import (
    FeatureScoringPolicyCode,
    FeatureScoringPolicyVersion,
    RankingPolicyCode,
    RankingPolicyVersion,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import ExchangeCalendarCode, ExchangeCalendarVersion
from auto_trading_v2.domain.outcome_labels import OutcomeLabelPolicyCode, OutcomeLabelPolicyVersion
from auto_trading_v2.domain.primitives import ProbabilityCalibrationDatasetID, SessionDate


def map_probability_calibration_dataset(row: Mapping[Any, Any]) -> ProbabilityCalibrationDataset:
    try:
        identity = ProbabilityCalibrationDatasetIdentity(
            CalibrationDatasetPolicyCode(_string(row["dataset_policy_code"])),
            CalibrationDatasetPolicyVersion(_string(row["dataset_policy_version"])),
            OutcomeLabelPolicyCode(_string(row["label_policy_code"])),
            OutcomeLabelPolicyVersion(_string(row["label_policy_version"])),
            OutcomeObservationPolicyCode(_string(row["outcome_policy_code"])),
            OutcomeObservationPolicyVersion(_string(row["outcome_policy_version"])),
            FeatureScoringPolicyCode(_string(row["scoring_policy_code"])),
            FeatureScoringPolicyVersion(_string(row["scoring_policy_version"])),
            RankingPolicyCode(_string(row["ranking_policy_code"])),
            RankingPolicyVersion(_string(row["ranking_policy_version"])),
            _string(row["provider_code"]),
            ExchangeCalendarCode(_string(row["calendar_code"])),
            ExchangeCalendarVersion(_string(row["calendar_version"])),
            TradingDayHorizon(_integer(row["horizon_trading_days"])),
            _datetime(row["dataset_as_of"]),
        )
        return ProbabilityCalibrationDataset(
            probability_calibration_dataset_id=ProbabilityCalibrationDatasetID(
                _uuid(row["probability_calibration_dataset_id"])
            ),
            dataset_key=_string(row["dataset_key"]),
            content_digest=_string(row["content_digest"]),
            identity=identity,
            status=ProbabilityCalibrationDatasetStatus(_string(row["status"])),
            total_count=_integer(row["total_count"]),
            positive_count=_integer(row["positive_count"]),
            not_positive_count=_integer(row["not_positive_count"]),
            prospective_count=_integer(row["prospective_count"]),
            retrospective_replay_count=_integer(row["retrospective_replay_count"]),
            unique_source_session_count=_integer(row["unique_source_session_count"]),
            earliest_source_session_date=_optional_session(row["earliest_source_session_date"]),
            latest_source_session_date=_optional_session(row["latest_source_session_date"]),
            generated_at=_datetime(row["generated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("probability_calibration_dataset") from None


def new_probability_calibration_dataset_values(
    candidate: NewProbabilityCalibrationDatasetWithItems,
) -> dict[str, object]:
    value = candidate.aggregate.dataset
    identity = value.identity
    return {
        "probability_calibration_dataset_id": value.probability_calibration_dataset_id.value,
        "dataset_key": value.dataset_key,
        "content_digest": value.content_digest,
        "dataset_policy_code": identity.dataset_policy_code.value,
        "dataset_policy_version": identity.dataset_policy_version.value,
        "label_policy_code": identity.label_policy_code.value,
        "label_policy_version": identity.label_policy_version.value,
        "outcome_policy_code": identity.outcome_policy_code.value,
        "outcome_policy_version": identity.outcome_policy_version.value,
        "scoring_policy_code": identity.scoring_policy_code.value,
        "scoring_policy_version": identity.scoring_policy_version.value,
        "ranking_policy_code": identity.ranking_policy_code.value,
        "ranking_policy_version": identity.ranking_policy_version.value,
        "provider_code": identity.provider_code,
        "calendar_code": identity.calendar_code.value,
        "calendar_version": identity.calendar_version.value,
        "horizon_trading_days": identity.horizon.value,
        "dataset_as_of": identity.dataset_as_of,
        "status": value.status.value,
        "total_count": value.total_count,
        "positive_count": value.positive_count,
        "not_positive_count": value.not_positive_count,
        "prospective_count": value.prospective_count,
        "retrospective_replay_count": value.retrospective_replay_count,
        "unique_source_session_count": value.unique_source_session_count,
        "earliest_source_session_date": None
        if value.earliest_source_session_date is None
        else value.earliest_source_session_date.value,
        "latest_source_session_date": None
        if value.latest_source_session_date is None
        else value.latest_source_session_date.value,
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


def _optional_session(value: object) -> SessionDate | None:
    return None if value is None else SessionDate(_date(value))


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
