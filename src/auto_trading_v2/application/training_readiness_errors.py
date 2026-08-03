"""Credential-safe application errors for readiness audits."""


class TrainingReadinessAuditError(RuntimeError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class TrainingReadinessDatasetNotFoundError(TrainingReadinessAuditError):
    def __init__(self) -> None:
        super().__init__("TRAINING_READINESS_DATASET_NOT_FOUND")
