"""Persistable P4B.2A calibration-dataset states."""

from enum import StrEnum


class ProbabilityCalibrationDatasetStatus(StrEnum):
    READY = "READY"
    EMPTY = "EMPTY"
