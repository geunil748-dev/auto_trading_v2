"""Sanitized P3 orchestration failures."""


class UniverseSnapshotNotFoundError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("UniverseSnapshot was not found")


class DailyFeaturePipelineRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature pipeline unique race could not be resolved")


class DailyFeaturePipelinePersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("daily feature pipeline summary persistence failed")
