"""Insert-only P4B.2A dataset persistence with unique-race resolution."""

from dataclasses import dataclass
from enum import StrEnum

from auto_trading_v2.application.calibration_dataset_errors import (
    ProbabilityCalibrationDatasetConflictError,
    ProbabilityCalibrationDatasetPersistenceError,
    ProbabilityCalibrationDatasetRaceResolutionError,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetWithItems,
)


class CanonicalDatasetStoreDisposition(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class CanonicalDatasetStoreResult:
    disposition: CanonicalDatasetStoreDisposition
    aggregate: ProbabilityCalibrationDatasetWithItems


@dataclass(frozen=True, slots=True)
class ProbabilityCalibrationDatasetStore:
    unit_of_work_factory: UnitOfWorkFactory

    def existing(self, dataset_key: str) -> ProbabilityCalibrationDatasetWithItems | None:
        with self.unit_of_work_factory() as unit_of_work:
            dataset = unit_of_work.probability_calibration_datasets.get_by_dataset_key(dataset_key)
            if dataset is None:
                return None
            aggregate = unit_of_work.probability_calibration_datasets.get_dataset_with_items(
                dataset.probability_calibration_dataset_id
            )
        if aggregate is None:
            raise ProbabilityCalibrationDatasetPersistenceError()
        return aggregate

    def persist(
        self, candidate: NewProbabilityCalibrationDatasetWithItems
    ) -> CanonicalDatasetStoreResult:
        try:
            with self.unit_of_work_factory() as unit_of_work:
                try:
                    stored = unit_of_work.probability_calibration_datasets.add_dataset_with_items(
                        candidate
                    )
                except DuplicateRecordError:
                    unit_of_work.rollback()
                else:
                    unit_of_work.commit()
                    return CanonicalDatasetStoreResult(
                        CanonicalDatasetStoreDisposition.CREATED,
                        stored,
                    )
        except PersistenceError:
            raise ProbabilityCalibrationDatasetPersistenceError() from None
        existing = self.existing(candidate.aggregate.dataset.dataset_key)
        if existing is None:
            raise ProbabilityCalibrationDatasetRaceResolutionError()
        if existing.dataset.content_digest != candidate.aggregate.dataset.content_digest:
            raise ProbabilityCalibrationDatasetConflictError()
        return CanonicalDatasetStoreResult(
            CanonicalDatasetStoreDisposition.ALREADY_EXISTS,
            existing,
        )
