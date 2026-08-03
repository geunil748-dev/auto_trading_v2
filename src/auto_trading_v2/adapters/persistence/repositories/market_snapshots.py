"""SQLAlchemy Core market-snapshot repository."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.mapping import map_market_snapshot
from auto_trading_v2.adapters.persistence.tables import market_snapshots
from auto_trading_v2.application.contracts.persistence import (
    NewMarketSnapshot,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import MarketSnapshotID, Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc


def _allow_operation() -> None:
    return None


class SqlAlchemyMarketSnapshotRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, snapshot: NewMarketSnapshot) -> StoredMarketSnapshot:
        self._ensure_active()
        values = {
            "market_snapshot_id": snapshot.market_snapshot_id.value,
            "symbol": snapshot.symbol.value,
            "session_date": snapshot.session_date.value,
            "observed_at": snapshot.observed_at,
            "source": snapshot.source,
            "open_price": snapshot.open_price.value,
            "high_price": snapshot.high_price.value,
            "low_price": snapshot.low_price.value,
            "last_price": snapshot.last_price.value,
            "previous_high_price": snapshot.previous_high_price.value,
            "previous_low_price": snapshot.previous_low_price.value,
            "previous_close_price": (
                None
                if snapshot.previous_close_price is None
                else snapshot.previous_close_price.value
            ),
            "volume": snapshot.volume,
        }
        try:
            self._connection.execute(market_snapshots.insert().values(**values))
            stored = self._select(snapshot.market_snapshot_id)
            if stored is None:
                raise PersistenceMappingError("market_snapshot", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="market_snapshot", operation="insert"
            ) from None

    def get(self, market_snapshot_id: MarketSnapshotID) -> StoredMarketSnapshot | None:
        self._ensure_active()
        try:
            return self._select(market_snapshot_id)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="market_snapshot", operation="select"
            ) from None

    def get_by_observation(
        self, *, source: str, symbol: Symbol, observed_at: datetime
    ) -> StoredMarketSnapshot | None:
        self._ensure_active()
        try:
            row = (
                self._connection.execute(
                    select(market_snapshots).where(
                        market_snapshots.c.source == source,
                        market_snapshots.c.symbol == symbol.value,
                        market_snapshots.c.observed_at == normalize_utc(observed_at),
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else map_market_snapshot(row)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="market_snapshot", operation="select"
            ) from None

    def _select(self, market_snapshot_id: MarketSnapshotID) -> StoredMarketSnapshot | None:
        row = (
            self._connection.execute(
                select(market_snapshots).where(
                    market_snapshots.c.market_snapshot_id == market_snapshot_id.value
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_market_snapshot(row)
