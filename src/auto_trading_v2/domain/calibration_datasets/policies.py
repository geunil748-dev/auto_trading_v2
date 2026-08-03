"""Frozen P4B.2A calibration-dataset policy values."""

from dataclasses import dataclass

from auto_trading_v2.domain.calibration_datasets.errors import (
    ProbabilityCalibrationDatasetValidationError,
)

DATASET_POLICY_CODE = "READY_SCORE_POSITIVE_CLOSE_CALIBRATION_DATASET"
DATASET_POLICY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class _PolicyValue:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value:
            raise ProbabilityCalibrationDatasetValidationError("DATASET_POLICY_VALUE_INVALID")


class CalibrationDatasetPolicyCode(_PolicyValue):
    __slots__ = ()


class CalibrationDatasetPolicyVersion(_PolicyValue):
    __slots__ = ()


def fixed_dataset_policy_values() -> tuple[
    CalibrationDatasetPolicyCode,
    CalibrationDatasetPolicyVersion,
]:
    return (
        CalibrationDatasetPolicyCode(DATASET_POLICY_CODE),
        CalibrationDatasetPolicyVersion(DATASET_POLICY_VERSION),
    )
