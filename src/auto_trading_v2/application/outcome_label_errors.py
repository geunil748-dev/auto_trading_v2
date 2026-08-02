"""Payload-safe P4B.2A label application failures."""


class DailyFeatureOutcomeLabelSourceNotFoundError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome label source was not found")


class DailyFeatureOutcomeLabelPersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome label persistence failed")


class DailyFeatureOutcomeLabelRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome label unique race could not be resolved")


class DailyFeatureOutcomeLabelConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature outcome label content conflict")
