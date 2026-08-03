"""Semantic identity for immutable P4B.2A dataset snapshots."""

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.calibration_datasets.errors import (
    ProbabilityCalibrationDatasetValidationError,
)
from auto_trading_v2.domain.calibration_datasets.policies import (
    DATASET_POLICY_CODE,
    DATASET_POLICY_VERSION,
    CalibrationDatasetPolicyCode,
    CalibrationDatasetPolicyVersion,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    SOURCE_PROVIDER_CODE,
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
    outcome_content_digest,
)
from auto_trading_v2.domain.feature_scoring import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
    FeatureScoringPolicyCode,
    FeatureScoringPolicyVersion,
    RankingPolicyCode,
    RankingPolicyVersion,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import ExchangeCalendarCode, ExchangeCalendarVersion
from auto_trading_v2.domain.outcome_labels import (
    LABEL_POLICY_CODE,
    LABEL_POLICY_VERSION,
    OutcomeLabelPolicyCode,
    OutcomeLabelPolicyVersion,
)
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDatasetIdentity:
    dataset_policy_code: CalibrationDatasetPolicyCode
    dataset_policy_version: CalibrationDatasetPolicyVersion
    label_policy_code: OutcomeLabelPolicyCode
    label_policy_version: OutcomeLabelPolicyVersion
    outcome_policy_code: OutcomeObservationPolicyCode
    outcome_policy_version: OutcomeObservationPolicyVersion
    scoring_policy_code: FeatureScoringPolicyCode
    scoring_policy_version: FeatureScoringPolicyVersion
    ranking_policy_code: RankingPolicyCode
    ranking_policy_version: RankingPolicyVersion
    provider_code: str
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    horizon: TradingDayHorizon
    dataset_as_of: datetime

    def __post_init__(self) -> None:
        values = (
            self.dataset_policy_code.value,
            self.dataset_policy_version.value,
            self.label_policy_code.value,
            self.label_policy_version.value,
            self.outcome_policy_code.value,
            self.outcome_policy_version.value,
            self.scoring_policy_code.value,
            self.scoring_policy_version.value,
            self.ranking_policy_code.value,
            self.ranking_policy_version.value,
            self.provider_code,
            self.calendar_code.value,
            self.calendar_version.value,
        )
        expected = (
            DATASET_POLICY_CODE,
            DATASET_POLICY_VERSION,
            LABEL_POLICY_CODE,
            LABEL_POLICY_VERSION,
            OUTCOME_POLICY_CODE,
            OUTCOME_POLICY_VERSION,
            SCORING_POLICY_CODE,
            SCORING_POLICY_VERSION,
            RANKING_POLICY_CODE,
            RANKING_POLICY_VERSION,
            SOURCE_PROVIDER_CODE,
            CALENDAR_CODE,
            CALENDAR_VERSION,
        )
        if values != expected or not isinstance(self.horizon, TradingDayHorizon):
            _invalid("DATASET_POLICY_UNSUPPORTED")
        try:
            normalized = normalize_utc(self.dataset_as_of)
        except (TypeError, ValidationError):
            _invalid("DATASET_AS_OF_INVALID")
        object.__setattr__(self, "dataset_as_of", normalized)


def calibration_dataset_key(identity: ProbabilityCalibrationDatasetIdentity) -> str:
    payload = {
        "calendar_code": identity.calendar_code.value,
        "calendar_version": identity.calendar_version.value,
        "dataset_as_of": UtcTimestamp(identity.dataset_as_of).serialize(),
        "dataset_policy_code": identity.dataset_policy_code.value,
        "dataset_policy_version": identity.dataset_policy_version.value,
        "horizon_trading_days": identity.horizon.value,
        "label_policy_code": identity.label_policy_code.value,
        "label_policy_version": identity.label_policy_version.value,
        "outcome_policy_code": identity.outcome_policy_code.value,
        "outcome_policy_version": identity.outcome_policy_version.value,
        "provider_code": identity.provider_code,
        "ranking_policy_code": identity.ranking_policy_code.value,
        "ranking_policy_version": identity.ranking_policy_version.value,
        "scoring_policy_code": identity.scoring_policy_code.value,
        "scoring_policy_version": identity.scoring_policy_version.value,
    }
    return f"probability-calibration-dataset:v1:{outcome_content_digest(payload)}"


def _invalid(category: str) -> None:
    raise ProbabilityCalibrationDatasetValidationError(category)
