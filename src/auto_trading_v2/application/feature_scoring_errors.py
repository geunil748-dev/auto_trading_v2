"""Payload-safe P4A application failures."""


class DailyFeatureScoringPersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature scoring persistence failed")


class DailyFeatureScoringRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature scoring unique race could not be resolved")


class DailyFeatureScoringConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature scoring content conflict")
