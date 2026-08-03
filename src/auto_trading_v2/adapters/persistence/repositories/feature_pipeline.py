"""SQLAlchemy Core repository for immutable P3 run aggregates."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.feature_pipeline_mapping import (
    map_pipeline_item,
    map_pipeline_run,
    new_pipeline_item_values,
    new_pipeline_run_values,
)
from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItem,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.primitives import DailyFeaturePipelineRunID


def _allow_operation() -> None:
    return None


class SqlAlchemyDailyFeaturePipelineRunRepository:
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
        self,
        aggregate: NewDailyFeaturePipelineRunWithItems,
    ) -> DailyFeaturePipelineRunWithItems:
        self._ensure_active()
        try:
            self._connection.execute(
                daily_feature_pipeline_runs.insert().values(
                    **new_pipeline_run_values(aggregate.run)
                )
            )
            for item in aggregate.items:
                self._connection.execute(
                    daily_feature_pipeline_items.insert().values(**new_pipeline_item_values(item))
                )
            stored = self._select_aggregate(aggregate.run.daily_feature_pipeline_run_id)
            if stored is None:
                raise PersistenceMappingError("daily_feature_pipeline_run", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_pipeline_run",
                operation="insert",
            ) from None

    def get_by_id(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> DailyFeaturePipelineRun | None:
        self._ensure_active()
        return self._read_run(
            daily_feature_pipeline_runs.c.daily_feature_pipeline_run_id == run_id.value
        )

    def get_by_run_key(self, run_key: str) -> DailyFeaturePipelineRun | None:
        self._ensure_active()
        return self._read_run(daily_feature_pipeline_runs.c.run_key == run_key)

    def list_items(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> tuple[DailyFeaturePipelineItem, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(daily_feature_pipeline_items)
                    .where(
                        daily_feature_pipeline_items.c.daily_feature_pipeline_run_id == run_id.value
                    )
                    .order_by(daily_feature_pipeline_items.c.ordinal.asc())
                )
                .mappings()
                .all()
            )
            return tuple(map_pipeline_item(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_pipeline_item",
                operation="select",
            ) from None

    def get_run_with_items(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> DailyFeaturePipelineRunWithItems | None:
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
                entity="daily_feature_pipeline_run",
                operation="select",
            ) from None

    def _select_aggregate(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> DailyFeaturePipelineRunWithItems | None:
        run = self._select_run(
            daily_feature_pipeline_runs.c.daily_feature_pipeline_run_id == run_id.value
        )
        if run is None:
            return None
        rows = (
            self._connection.execute(
                select(daily_feature_pipeline_items)
                .where(daily_feature_pipeline_items.c.daily_feature_pipeline_run_id == run_id.value)
                .order_by(daily_feature_pipeline_items.c.ordinal.asc())
            )
            .mappings()
            .all()
        )
        return DailyFeaturePipelineRunWithItems(
            run,
            tuple(map_pipeline_item(row) for row in rows),
        )

    def _read_run(
        self,
        *criteria: ColumnElement[bool],
    ) -> DailyFeaturePipelineRun | None:
        try:
            return self._select_run(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_feature_pipeline_run",
                operation="select",
            ) from None

    def _select_run(
        self,
        *criteria: ColumnElement[bool],
    ) -> DailyFeaturePipelineRun | None:
        row = (
            self._connection.execute(select(daily_feature_pipeline_runs).where(*criteria))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_pipeline_run(row)
