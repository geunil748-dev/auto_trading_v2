"""P4B.2A versioned positive-close outcome labels."""

from auto_trading_v2.domain.outcome_labels.errors import OutcomeLabelValidationError
from auto_trading_v2.domain.outcome_labels.identity import (
    DailyFeatureOutcomeLabelIdentity,
    outcome_label_content_digest,
    outcome_label_key,
)
from auto_trading_v2.domain.outcome_labels.labels import (
    positive_forward_close_label,
    validate_label_source,
)
from auto_trading_v2.domain.outcome_labels.models import DailyFeatureOutcomeLabel
from auto_trading_v2.domain.outcome_labels.outcomes import PositiveForwardCloseLabel
from auto_trading_v2.domain.outcome_labels.policies import (
    LABEL_POLICY_CODE,
    LABEL_POLICY_VERSION,
    OutcomeLabelPolicyCode,
    OutcomeLabelPolicyVersion,
    fixed_label_policy_values,
)

__all__ = [
    "DailyFeatureOutcomeLabel",
    "DailyFeatureOutcomeLabelIdentity",
    "LABEL_POLICY_CODE",
    "LABEL_POLICY_VERSION",
    "OutcomeLabelPolicyCode",
    "OutcomeLabelPolicyVersion",
    "OutcomeLabelValidationError",
    "PositiveForwardCloseLabel",
    "fixed_label_policy_values",
    "outcome_label_content_digest",
    "outcome_label_key",
    "positive_forward_close_label",
    "validate_label_source",
]
