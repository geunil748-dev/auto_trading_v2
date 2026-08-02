"""Deterministic identity and content hashes for P4B.2A labels."""

from dataclasses import dataclass

from auto_trading_v2.domain.feature_outcomes import DailyFeatureOutcome, outcome_content_digest
from auto_trading_v2.domain.outcome_labels.errors import OutcomeLabelValidationError
from auto_trading_v2.domain.outcome_labels.outcomes import PositiveForwardCloseLabel
from auto_trading_v2.domain.outcome_labels.policies import (
    LABEL_POLICY_CODE,
    LABEL_POLICY_VERSION,
    OutcomeLabelPolicyCode,
    OutcomeLabelPolicyVersion,
)
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeID, UtcTimestamp


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeLabelIdentity:
    source_daily_feature_outcome_id: DailyFeatureOutcomeID
    label_policy_code: OutcomeLabelPolicyCode
    label_policy_version: OutcomeLabelPolicyVersion

    def __post_init__(self) -> None:
        if not isinstance(self.source_daily_feature_outcome_id, DailyFeatureOutcomeID):
            _invalid("LABEL_SOURCE_OUTCOME_ID_INVALID")
        if (self.label_policy_code.value, self.label_policy_version.value) != (
            LABEL_POLICY_CODE,
            LABEL_POLICY_VERSION,
        ):
            _invalid("LABEL_POLICY_UNSUPPORTED")


def outcome_label_key(identity: DailyFeatureOutcomeLabelIdentity) -> str:
    payload = {
        "label_policy_code": identity.label_policy_code.value,
        "label_policy_version": identity.label_policy_version.value,
        "source_daily_feature_outcome_id": identity.source_daily_feature_outcome_id.serialize(),
    }
    return f"daily-feature-outcome-label:v1:{outcome_content_digest(payload)}"


def outcome_label_content_digest(
    source: DailyFeatureOutcome,
    label_policy_code: OutcomeLabelPolicyCode,
    label_policy_version: OutcomeLabelPolicyVersion,
    label_value: PositiveForwardCloseLabel,
) -> str:
    payload = {
        "feature_snapshot_id": source.feature_snapshot_id.serialize(),
        "horizon_trading_days": source.horizon.value,
        "label_policy_code": label_policy_code.value,
        "label_policy_version": label_policy_version.value,
        "label_value": label_value.value,
        "mic_code": source.mic_code,
        "observation_mode": source.observation_mode.value,
        "source_daily_feature_outcome_id": source.daily_feature_outcome_id.serialize(),
        "source_daily_feature_outcome_key": source.outcome_key,
        "source_daily_feature_outcome_content_digest": source.content_digest,
        "source_daily_feature_pipeline_item_id": (
            source.source_daily_feature_pipeline_item_id.serialize()
        ),
        "source_daily_feature_pipeline_run_id": (
            source.source_daily_feature_pipeline_run_id.serialize()
        ),
        "source_daily_feature_scoring_item_id": (
            source.source_daily_feature_scoring_item_id.serialize()
        ),
        "source_daily_feature_scoring_run_id": (
            source.source_daily_feature_scoring_run_id.serialize()
        ),
        "source_latest_input_available_at": UtcTimestamp(
            source.latest_input_available_at
        ).serialize(),
        "source_path_revision_digest": source.path_revision_digest,
        "source_session_date": source.source_session_date.serialize(),
        "symbol": source.symbol.serialize(),
        "terminal_session_date": source.terminal_session_date.serialize(),
    }
    return outcome_content_digest(payload)


def _invalid(category: str) -> None:
    raise OutcomeLabelValidationError(category)
