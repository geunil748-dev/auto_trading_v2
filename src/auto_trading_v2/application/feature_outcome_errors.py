"""Payload-safe P4B.1 application failures."""


class DailyFeatureOutcomePersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome persistence failed")


class DailyFeatureOutcomeRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome unique race could not be resolved")


class DailyFeatureOutcomeConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome content conflict")


class DailyFeatureOutcomeObservationRunPersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome observation run persistence failed")


class DailyFeatureOutcomeObservationRunRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome observation run race could not be resolved")


class DailyFeatureOutcomeObservationRunConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome observation run content conflict")
