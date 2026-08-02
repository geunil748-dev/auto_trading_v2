"""SQLAlchemy Core repository for immutable P4B.2A dataset aggregates."""

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.calibration_dataset_item_mapping import (
    map_probability_calibration_dataset_item,
    new_probability_calibration_dataset_item_values,
)
from auto_trading_v2.adapters.persistence.calibration_dataset_mapping import (
    map_probability_calibration_dataset,
    new_probability_calibration_dataset_values,
)
from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import (
    probability_calibration_dataset_items,
    probability_calibration_datasets,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.primitives import ProbabilityCalibrationDatasetID


def _allow_operation() -> None:
    return None


class SqlAlchemyProbabilityCalibrationDatasetRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add_dataset_with_items(
        self, candidate: NewProbabilityCalibrationDatasetWithItems
    ) -> ProbabilityCalibrationDatasetWithItems:
        self._ensure_active()
        try:
            self._connection.execute(
                probability_calibration_datasets.insert().values(
                    **new_probability_calibration_dataset_values(candidate)
                )
            )
            for item in candidate.aggregate.items:
                self._connection.execute(
                    probability_calibration_dataset_items.insert().values(
                        **new_probability_calibration_dataset_item_values(item)
                    )
                )
            stored = self._select_aggregate(
                candidate.aggregate.dataset.probability_calibration_dataset_id
            )
            if stored is None:
                raise PersistenceMappingError("probability_calibration_dataset", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="probability_calibration_dataset", operation="insert"
            ) from None

    def get_by_id(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> ProbabilityCalibrationDataset | None:
        self._ensure_active()
        return self._read(
            probability_calibration_datasets.c.probability_calibration_dataset_id
            == dataset_id.value
        )

    def get_by_dataset_key(self, dataset_key: str) -> ProbabilityCalibrationDataset | None:
        self._ensure_active()
        return self._read(probability_calibration_datasets.c.dataset_key == dataset_key)

    def list_items(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> tuple[ProbabilityCalibrationDatasetItem, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(probability_calibration_dataset_items)
                    .where(
                        probability_calibration_dataset_items.c.probability_calibration_dataset_id
                        == dataset_id.value
                    )
                    .order_by(probability_calibration_dataset_items.c.ordinal.asc())
                )
                .mappings()
                .all()
            )
            return tuple(map_probability_calibration_dataset_item(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="probability_calibration_dataset_item", operation="select"
            ) from None

    def get_dataset_with_items(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> ProbabilityCalibrationDatasetWithItems | None:
        self._ensure_active()
        try:
            return self._select_aggregate(dataset_id)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="probability_calibration_dataset", operation="select"
            ) from None

    def _select_aggregate(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> ProbabilityCalibrationDatasetWithItems | None:
        dataset = self._select(
            probability_calibration_datasets.c.probability_calibration_dataset_id
            == dataset_id.value
        )
        return (
            None
            if dataset is None
            else ProbabilityCalibrationDatasetWithItems(dataset, self.list_items(dataset_id))
        )

    def _read(self, *criteria: ColumnElement[bool]) -> ProbabilityCalibrationDataset | None:
        try:
            return self._select(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="probability_calibration_dataset", operation="select"
            ) from None

    def _select(self, *criteria: ColumnElement[bool]) -> ProbabilityCalibrationDataset | None:
        row = (
            self._connection.execute(select(probability_calibration_datasets).where(*criteria))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_probability_calibration_dataset(row)
