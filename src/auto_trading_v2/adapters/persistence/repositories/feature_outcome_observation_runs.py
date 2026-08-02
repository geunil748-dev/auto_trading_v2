"""SQLAlchemy Core repository for immutable P4B.1 observation audits."""

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.feature_outcome_observation_mapping import (
    map_outcome_observation_item,
    map_outcome_observation_run,
    new_outcome_observation_item_values,
    new_outcome_observation_run_values,
)
from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_outcome_observation_run_items,
    daily_feature_outcome_observation_runs,
)
from auto_trading_v2.application.contracts.feature_outcomes import (
    NewDailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunItem,
    DailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeObservationRunID


def _allow_operation() -> None:
    return None


class SqlAlchemyDailyFeatureOutcomeObservationRunRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add_run_with_items(
        self, candidate: NewDailyFeatureOutcomeObservationRunWithItems
    ) -> DailyFeatureOutcomeObservationRunWithItems:
        self._ensure_active()
        try:
            self._connection.execute(
                daily_feature_outcome_observation_runs.insert().values(
                    **new_outcome_observation_run_values(candidate)
                )
            )
            for item in candidate.aggregate.items:
                self._connection.execute(
                    daily_feature_outcome_observation_run_items.insert().values(
                        **new_outcome_observation_item_values(item)
                    )
                )
            stored = self._select_aggregate(
                candidate.aggregate.run.daily_feature_outcome_observation_run_id
            )
            if stored is None:
                raise PersistenceMappingError("daily_feature_outcome_observation_run", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_outcome_observation_run",
                operation="insert",
            ) from None

    def get_by_id(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> DailyFeatureOutcomeObservationRun | None:
        self._ensure_active()
        return self._read_run(
            daily_feature_outcome_observation_runs.c.daily_feature_outcome_observation_run_id
            == run_id.value
        )

    def get_by_observation_run_key(
        self, observation_run_key: str
    ) -> DailyFeatureOutcomeObservationRun | None:
        self._ensure_active()
        return self._read_run(
            daily_feature_outcome_observation_runs.c.observation_run_key == observation_run_key
        )

    def list_items(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> tuple[DailyFeatureOutcomeObservationRunItem, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(daily_feature_outcome_observation_run_items)
                    .where(
                        daily_feature_outcome_observation_run_items.c.daily_feature_outcome_observation_run_id
                        == run_id.value
                    )
                    .order_by(daily_feature_outcome_observation_run_items.c.ordinal.asc())
                )
                .mappings()
                .all()
            )
            return tuple(map_outcome_observation_item(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_outcome_observation_run_item",
                operation="select",
            ) from None

    def get_run_with_items(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> DailyFeatureOutcomeObservationRunWithItems | None:
        self._ensure_active()
        try:
            return self._select_aggregate(run_id)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_outcome_observation_run",
                operation="select",
            ) from None

    def _select_aggregate(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> DailyFeatureOutcomeObservationRunWithItems | None:
        run = self._select_run(
            daily_feature_outcome_observation_runs.c.daily_feature_outcome_observation_run_id
            == run_id.value
        )
        if run is None:
            return None
        return DailyFeatureOutcomeObservationRunWithItems(run, self.list_items(run_id))

    def _read_run(self, *criteria: ColumnElement[bool]) -> DailyFeatureOutcomeObservationRun | None:
        try:
            return self._select_run(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_outcome_observation_run",
                operation="select",
            ) from None

    def _select_run(
        self, *criteria: ColumnElement[bool]
    ) -> DailyFeatureOutcomeObservationRun | None:
        row = (
            self._connection.execute(
                select(daily_feature_outcome_observation_runs).where(*criteria)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_outcome_observation_run(row)
