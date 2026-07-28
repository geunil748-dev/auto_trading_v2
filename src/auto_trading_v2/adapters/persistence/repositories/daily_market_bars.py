"""SQLAlchemy Core repository for immutable DailyMarketBar records."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Connection, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.base import Executable

from auto_trading_v2.adapters.persistence.daily_market_bar_mapping import (
    map_daily_market_bar,
    new_daily_market_bar_values,
)
from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import daily_market_bars
from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import DailyMarketBarID, Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc


def _allow_operation() -> None:
    return None


class SqlAlchemyDailyMarketBarRepository:
    """Insert and PIT-query bars in the caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, bar: NewDailyMarketBar) -> DailyMarketBar:
        self._ensure_active()
        try:
            self._connection.execute(
                daily_market_bars.insert().values(**new_daily_market_bar_values(bar))
            )
            stored = self._select_by_id(bar.daily_market_bar_id)
            if stored is None:
                raise PersistenceMappingError("daily_market_bar", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_market_bar",
                operation="insert",
            ) from None

    def get_by_id(self, daily_market_bar_id: DailyMarketBarID) -> DailyMarketBar | None:
        self._ensure_active()
        return self._read(
            select(daily_market_bars).where(
                daily_market_bars.c.daily_market_bar_id == daily_market_bar_id.value
            )
        )

    def get_by_bar_key(self, bar_key: str) -> DailyMarketBar | None:
        self._ensure_active()
        return self._read(select(daily_market_bars).where(daily_market_bars.c.bar_key == bar_key))

    def get_by_source_identity(
        self,
        source_code: str,
        source_record_key: str,
        source_version: str,
    ) -> DailyMarketBar | None:
        self._ensure_active()
        return self._read(
            select(daily_market_bars).where(
                daily_market_bars.c.source_code == source_code,
                daily_market_bars.c.source_record_key == source_record_key,
                daily_market_bars.c.source_version == source_version,
            )
        )

    def list_latest_available(
        self,
        source_code: str,
        symbol: Symbol,
        adjustment_basis: DailyMarketBarAdjustmentBasis,
        as_of: datetime,
        limit: int,
    ) -> tuple[DailyMarketBar, ...]:
        self._ensure_active()
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be at least one")
        if not isinstance(symbol, Symbol):
            raise TypeError("symbol must be Symbol")
        if not isinstance(adjustment_basis, DailyMarketBarAdjustmentBasis):
            raise TypeError("adjustment_basis is invalid")
        try:
            cutoff = normalize_utc(as_of)
        except ValidationError:
            raise ValueError("as_of must be timezone-aware") from None
        statement = latest_available_daily_market_bars_statement(
            source_code,
            symbol,
            adjustment_basis,
            cutoff,
            limit,
        )
        try:
            rows = self._connection.execute(statement).mappings().all()
            return tuple(map_daily_market_bar(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_market_bar",
                operation="select",
            ) from None

    def _select_by_id(
        self,
        daily_market_bar_id: DailyMarketBarID,
    ) -> DailyMarketBar | None:
        return self._read(
            select(daily_market_bars).where(
                daily_market_bars.c.daily_market_bar_id == daily_market_bar_id.value
            )
        )

    def _read(self, statement: Executable) -> DailyMarketBar | None:
        try:
            row = self._connection.execute(statement).mappings().one_or_none()
            return None if row is None else map_daily_market_bar(row)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="daily_market_bar",
                operation="select",
            ) from None


def latest_available_daily_market_bars_statement(
    source_code: str,
    symbol: Symbol,
    adjustment_basis: DailyMarketBarAdjustmentBasis,
    as_of: datetime,
    limit: int,
) -> Executable:
    """Select the latest available revision for each of the latest sessions."""

    revision_rank = (
        func.row_number()
        .over(
            partition_by=daily_market_bars.c.session_date,
            order_by=(
                daily_market_bars.c.available_at.desc(),
                daily_market_bars.c.bar_key.desc(),
            ),
        )
        .label("_revision_rank")
    )
    ranked = (
        select(daily_market_bars, revision_rank)
        .where(
            daily_market_bars.c.source_code == source_code,
            daily_market_bars.c.symbol == symbol.value,
            daily_market_bars.c.adjustment_basis == adjustment_basis.value,
            daily_market_bars.c.available_at <= as_of,
        )
        .subquery("ranked_daily_market_bars")
    )
    column_names = tuple(column.name for column in daily_market_bars.c)
    recent = (
        select(*(ranked.c[name] for name in column_names))
        .where(ranked.c._revision_rank == 1)
        .order_by(ranked.c.session_date.desc())
        .limit(limit)
        .subquery("recent_daily_market_bars")
    )
    return select(*(recent.c[name] for name in column_names)).order_by(recent.c.session_date.asc())
