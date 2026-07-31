"""SQLAlchemy Core repository for immutable UniverseSnapshot records."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import universe_snapshots
from auto_trading_v2.adapters.persistence.universe_mapping import (
    map_universe_snapshot,
    new_universe_snapshot_values,
)
from auto_trading_v2.application.contracts.universes import NewUniverseSnapshot
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import UniverseSnapshotID
from auto_trading_v2.domain.universes import UniverseCode, UniverseSnapshot, UniverseVersion


def _allow_operation() -> None:
    return None


class SqlAlchemyUniverseSnapshotRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, snapshot: NewUniverseSnapshot) -> UniverseSnapshot:
        self._ensure_active()
        try:
            self._connection.execute(
                universe_snapshots.insert().values(**new_universe_snapshot_values(snapshot))
            )
            stored = self._select(
                universe_snapshots.c.universe_snapshot_id == snapshot.universe_snapshot_id.value
            )
            if stored is None:
                raise PersistenceMappingError("universe_snapshot", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="universe_snapshot",
                operation="insert",
            ) from None

    def get_by_id(self, universe_snapshot_id: UniverseSnapshotID) -> UniverseSnapshot | None:
        self._ensure_active()
        return self._read(universe_snapshots.c.universe_snapshot_id == universe_snapshot_id.value)

    def get_by_universe_key(self, universe_key: str) -> UniverseSnapshot | None:
        self._ensure_active()
        return self._read(universe_snapshots.c.universe_key == universe_key)

    def get_by_code_and_version(
        self,
        universe_code: UniverseCode,
        universe_version: UniverseVersion,
    ) -> UniverseSnapshot | None:
        self._ensure_active()
        return self._read(
            universe_snapshots.c.universe_code == universe_code.value,
            universe_snapshots.c.universe_version == universe_version.value,
        )

    def _read(self, *criteria: ColumnElement[bool]) -> UniverseSnapshot | None:
        try:
            return self._select(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="universe_snapshot",
                operation="select",
            ) from None

    def _select(self, *criteria: ColumnElement[bool]) -> UniverseSnapshot | None:
        row = (
            self._connection.execute(select(universe_snapshots).where(*criteria))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_universe_snapshot(row)
