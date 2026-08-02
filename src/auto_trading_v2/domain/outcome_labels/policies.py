"""Frozen P4B.2A positive-close label policy values."""

from dataclasses import dataclass

from auto_trading_v2.domain.outcome_labels.errors import OutcomeLabelValidationError

LABEL_POLICY_CODE = "US_EQUITY_POSITIVE_FORWARD_CLOSE_LABEL"
LABEL_POLICY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class _PolicyValue:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value:
            raise OutcomeLabelValidationError("LABEL_POLICY_VALUE_INVALID")


class OutcomeLabelPolicyCode(_PolicyValue):
    __slots__ = ()


class OutcomeLabelPolicyVersion(_PolicyValue):
    __slots__ = ()


def fixed_label_policy_values() -> tuple[OutcomeLabelPolicyCode, OutcomeLabelPolicyVersion]:
    return (
        OutcomeLabelPolicyCode(LABEL_POLICY_CODE),
        OutcomeLabelPolicyVersion(LABEL_POLICY_VERSION),
    )
