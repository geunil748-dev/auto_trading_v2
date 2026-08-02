"""Payload-safe P4B.2A dataset application failures."""


class ProbabilityCalibrationDatasetPersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("probability calibration dataset persistence failed")


class ProbabilityCalibrationDatasetRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("probability calibration dataset unique race could not be resolved")


class ProbabilityCalibrationDatasetConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("probability calibration dataset content conflict")
