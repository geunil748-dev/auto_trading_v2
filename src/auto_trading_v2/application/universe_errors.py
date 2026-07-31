"""Sanitized UniverseSnapshot application conflicts."""


class UniverseSnapshotConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("UniverseSnapshot semantic identity has different content")


class UniverseSnapshotRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("UniverseSnapshot unique race could not be resolved")
