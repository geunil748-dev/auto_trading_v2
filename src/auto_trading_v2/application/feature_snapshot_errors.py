"""Payload-safe application errors for FeatureSnapshot creation."""


class FeatureSnapshotConflictError(RuntimeError):
    """The semantic identity exists with different canonical content."""

    def __init__(self, snapshot_key: str) -> None:
        self.snapshot_key = snapshot_key
        super().__init__(f"feature snapshot content conflict: {snapshot_key}")


class FeatureSnapshotRaceResolutionError(RuntimeError):
    """A unique-write race could not be resolved to a canonical row."""

    def __init__(self) -> None:
        super().__init__("feature snapshot write race could not be resolved")
