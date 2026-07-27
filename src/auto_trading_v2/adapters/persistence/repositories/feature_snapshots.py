"""SQLAlchemy Core repository for immutable FeatureSnapshot records."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.feature_snapshot_mapping import (
    map_feature_snapshot,
    serialize_feature_values,
    serialize_provenance,
    serialize_quality_reasons,
)
from auto_trading_v2.adapters.persistence.tables import feature_snapshots
from auto_trading_v2.application.contracts.feature_snapshots import NewFeatureSnapshot
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_snapshots import FeatureSnapshot
from auto_trading_v2.domain.primitives import FeatureSnapshotID


def _allow_operation() -> None:
    return None


class SqlAlchemyFeatureSnapshotRepository:
    """Insert and read snapshots in the caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, snapshot: NewFeatureSnapshot) -> FeatureSnapshot:
        self._ensure_active()
        source = snapshot.snapshot_input
        values = {
            "feature_snapshot_id": snapshot.feature_snapshot_id.value,
            "snapshot_key": snapshot.snapshot_key,
            "content_digest": snapshot.content_digest,
            "symbol": source.symbol.value,
            "feature_set_code": source.feature_set_code,
            "feature_set_version": source.feature_set_version,
            "horizon_trading_days": source.horizon.value,
            "as_of": source.as_of,
            "generated_at": snapshot.generated_at,
            "latest_input_available_at": source.latest_input_available_at,
            "quality_status": source.quality_status.value,
            "quality_reason_codes": serialize_quality_reasons(source),
            "feature_values": serialize_feature_values(source),
            "provenance": serialize_provenance(source),
        }
        try:
            self._connection.execute(feature_snapshots.insert().values(**values))
            stored = self._select_by_id(snapshot.feature_snapshot_id)
            if stored is None:
                raise PersistenceMappingError("feature_snapshot", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="feature_snapshot",
                operation="insert",
            ) from None

    def get_by_id(self, feature_snapshot_id: FeatureSnapshotID) -> FeatureSnapshot | None:
        self._ensure_active()
        try:
            return self._select_by_id(feature_snapshot_id)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="feature_snapshot",
                operation="select",
            ) from None

    def get_by_snapshot_key(self, snapshot_key: str) -> FeatureSnapshot | None:
        self._ensure_active()
        try:
            row = (
                self._connection.execute(
                    select(feature_snapshots).where(
                        feature_snapshots.c.snapshot_key == snapshot_key
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else map_feature_snapshot(row)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="feature_snapshot",
                operation="select",
            ) from None

    def _select_by_id(
        self,
        feature_snapshot_id: FeatureSnapshotID,
    ) -> FeatureSnapshot | None:
        row = (
            self._connection.execute(
                select(feature_snapshots).where(
                    feature_snapshots.c.feature_snapshot_id == feature_snapshot_id.value
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_feature_snapshot(row)
