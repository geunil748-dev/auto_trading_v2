from dataclasses import replace
from datetime import UTC, datetime
from inspect import getmembers, isfunction
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

from sqlalchemy import Connection
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.daily_market_bar_mapping import (
    map_daily_market_bar,
    new_daily_market_bar_values,
)
from auto_trading_v2.adapters.persistence.repositories.daily_market_bars import (
    SqlAlchemyDailyMarketBarRepository,
    latest_available_daily_market_bars_statement,
)
from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.application.ports.daily_market_bars import DailyMarketBarRepository
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.primitives import DailyMarketBarID, Symbol
from tests.unit.domain.daily_market_bars.helpers import bar_input


def _new(index: int = 0) -> NewDailyMarketBar:
    source = bar_input(index)
    return NewDailyMarketBar(
        DailyMarketBarID(UUID(int=index + 1)),
        daily_market_bar_key(source),
        daily_market_bar_content_digest(source),
        source,
    )


def _row(value: NewDailyMarketBar | None = None) -> dict[str, object]:
    new = _new() if value is None else value
    return {
        **new_daily_market_bar_values(new),
        "recorded_at": datetime(2026, 2, 1, tzinfo=UTC),
    }


def test_repository_protocol_is_insert_only_with_pit_query() -> None:
    methods = {
        name
        for name, value in getmembers(DailyMarketBarRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {
        "add",
        "get_by_id",
        "get_by_bar_key",
        "list_latest_available",
    }
    assert not {"update", "delete", "upsert", "commit", "rollback"}.intersection(methods)


def test_mapping_round_trip_preserves_decimal_utc_date_and_nullable_volume() -> None:
    mapped = map_daily_market_bar(_row(_new()))
    nullable_source = replace(bar_input(), volume=None)
    nullable = NewDailyMarketBar(
        DailyMarketBarID(UUID(int=2)),
        daily_market_bar_key(nullable_source),
        daily_market_bar_content_digest(nullable_source),
        nullable_source,
    )
    nullable_row = _row(nullable)
    nullable_mapped = map_daily_market_bar(nullable_row)

    assert mapped.bar_input.close_price == bar_input().close_price
    assert mapped.bar_input.available_at.tzinfo is UTC
    assert mapped.bar_input.session_date == bar_input().session_date
    assert nullable_mapped.bar_input.volume is None


def test_add_and_getters_use_caller_connection_without_transaction_control() -> None:
    connection = MagicMock()
    selected = MagicMock()
    selected.mappings.return_value.one_or_none.return_value = _row()
    connection.execute.side_effect = [MagicMock(), selected]
    repository = SqlAlchemyDailyMarketBarRepository(cast(Connection, connection))

    stored = repository.add(_new())

    assert stored.daily_market_bar_id == DailyMarketBarID(UUID(int=1))
    assert connection.execute.call_count == 2
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_latest_available_maps_chronological_rows_and_exact_limit() -> None:
    connection = MagicMock()
    selected = MagicMock()
    second = _new(1)
    selected.mappings.return_value.all.return_value = [_row(), _row(second)]
    connection.execute.return_value = selected
    repository = SqlAlchemyDailyMarketBarRepository(cast(Connection, connection))
    as_of = datetime(2026, 3, 1, tzinfo=UTC)

    bars = repository.list_latest_available(
        "UNIT_SOURCE",
        Symbol("AAPL"),
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        as_of,
        21,
    )

    assert tuple(bar.bar_input.session_date for bar in bars) == (
        bar_input(0).session_date,
        bar_input(1).session_date,
    )
    compiled = str(
        connection.execute.call_args.args[0].compile(
            dialect=mssql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "row_number() OVER" in compiled
    assert "available_at <=" in compiled
    assert "TOP 21" in compiled
    assert "session_date ASC" in compiled


def test_shared_statement_is_deterministic_mssql_core_without_raw_sql() -> None:
    statement = latest_available_daily_market_bars_statement(
        "UNIT_SOURCE",
        Symbol("AAPL"),
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        datetime(2026, 3, 1, tzinfo=UTC),
        5,
    )
    compiled = str(
        statement.compile(
            dialect=mssql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "PARTITION BY" in compiled
    assert "available_at DESC" in compiled
    assert "bar_key DESC" in compiled
    assert "TOP 5" in compiled
    assert ";" not in compiled
