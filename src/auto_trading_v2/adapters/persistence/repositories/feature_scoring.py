"""SQLAlchemy Core repository for immutable P4A scoring aggregates."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.feature_scoring_mapping import (
    map_scoring_item,
    map_scoring_run,
    new_scoring_item_values,
    new_scoring_run_values,
)
from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
)
from auto_trading_v2.application.contracts.feature_scoring import (
    NewDailyFeatureScoringRunWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringItem,
    DailyFeatureScoringRun,
    DailyFeatureScoringRunWithItems,
)
from auto_trading_v2.domain.primitives import DailyFeatureScoringRunID


def _allow_operation() -> None:
    return None


class SqlAlchemyDailyFeatureScoringRunRepository:
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
        self, aggregate: NewDailyFeatureScoringRunWithItems
    ) -> DailyFeatureScoringRunWithItems:
        self._ensure_active()
        try:
            self._connection.execute(
                daily_feature_scoring_runs.insert().values(**new_scoring_run_values(aggregate.run))
            )
            for item in aggregate.items:
                self._connection.execute(
                    daily_feature_scoring_items.insert().values(**new_scoring_item_values(item))
                )
            stored = self._select_aggregate(aggregate.run.daily_feature_scoring_run_id)
            if stored is None:
                raise PersistenceMappingError("daily_feature_scoring_run", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_scoring_run", operation="insert"
            ) from None

    def get_by_id(self, run_id: DailyFeatureScoringRunID) -> DailyFeatureScoringRun | None:
        self._ensure_active()
        return self._read_run(
            daily_feature_scoring_runs.c.daily_feature_scoring_run_id == run_id.value
        )

    def get_by_scoring_run_key(self, scoring_run_key: str) -> DailyFeatureScoringRun | None:
        self._ensure_active()
        return self._read_run(daily_feature_scoring_runs.c.scoring_run_key == scoring_run_key)

    def list_items(self, run_id: DailyFeatureScoringRunID) -> tuple[DailyFeatureScoringItem, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(daily_feature_scoring_items)
                    .where(
                        daily_feature_scoring_items.c.daily_feature_scoring_run_id == run_id.value
                    )
                    .order_by(daily_feature_scoring_items.c.ordinal.asc())
                )
                .mappings()
                .all()
            )
            return tuple(map_scoring_item(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_scoring_item", operation="select"
            ) from None

    def get_run_with_items(
        self, run_id: DailyFeatureScoringRunID
    ) -> DailyFeatureScoringRunWithItems | None:
        self._ensure_active()
        try:
            return self._select_aggregate(run_id)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_scoring_run", operation="select"
            ) from None

    def _select_aggregate(
        self, run_id: DailyFeatureScoringRunID
    ) -> DailyFeatureScoringRunWithItems | None:
        run = self._select_run(
            daily_feature_scoring_runs.c.daily_feature_scoring_run_id == run_id.value
        )
        if run is None:
            return None
        rows = (
            self._connection.execute(
                select(daily_feature_scoring_items)
                .where(daily_feature_scoring_items.c.daily_feature_scoring_run_id == run_id.value)
                .order_by(daily_feature_scoring_items.c.ordinal.asc())
            )
            .mappings()
            .all()
        )
        return DailyFeatureScoringRunWithItems(run, tuple(map_scoring_item(row) for row in rows))

    def _read_run(self, *criteria: ColumnElement[bool]) -> DailyFeatureScoringRun | None:
        try:
            return self._select_run(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_scoring_run", operation="select"
            ) from None

    def _select_run(self, *criteria: ColumnElement[bool]) -> DailyFeatureScoringRun | None:
        row = (
            self._connection.execute(select(daily_feature_scoring_runs).where(*criteria))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_scoring_run(row)
