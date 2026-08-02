"""Frozen P4B.1 outcome-observation policy values."""

import re
from dataclasses import dataclass

from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)

OUTCOME_POLICY_CODE = "US_EQUITY_FORWARD_PATH_OBSERVATION"
OUTCOME_POLICY_VERSION = "v1"
SOURCE_PROVIDER_CODE = "TWELVE_DATA_TIME_SERIES"
CALENDAR_CODE = "US_EQUITY_CORE"
CALENDAR_VERSION = "2026.v1"
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class _PolicyValue:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CODE.fullmatch(self.value):
            raise OutcomeObservationValidationError("OUTCOME_POLICY_VALUE_INVALID")


class OutcomeObservationPolicyCode(_PolicyValue):
    __slots__ = ()


class OutcomeObservationPolicyVersion(_PolicyValue):
    __slots__ = ()


def fixed_outcome_policy_values() -> tuple[
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
]:
    return (
        OutcomeObservationPolicyCode(OUTCOME_POLICY_CODE),
        OutcomeObservationPolicyVersion(OUTCOME_POLICY_VERSION),
    )
