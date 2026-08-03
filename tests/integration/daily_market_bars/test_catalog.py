from uuid import UUID

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect, select
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.daily_market_bar_mapping import (
    new_daily_market_bar_values,
)
from auto_trading_v2.adapters.persistence.tables import daily_market_bars
from tests.integration.daily_market_bars.helpers import command, new_bar
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def test_live_daily_market_bar_catalog_matches_exact_metadata(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    inspector = inspect(mssql_database.engine)
    columns = inspector.get_columns("daily_market_bars", schema="trading")
    assert tuple(column["name"] for column in columns) == tuple(daily_market_bars.c.keys())
    assert len(columns) == 18
    assert inspector.get_pk_constraint("daily_market_bars", schema="trading")[
        "constrained_columns"
    ] == ["daily_market_bar_id"]
    assert inspector.get_foreign_keys("daily_market_bars", schema="trading") == []
    reflected_indexes = {
        index["name"] for index in inspector.get_indexes("daily_market_bars", schema="trading")
    }
    expected_indexes = {index.name for index in daily_market_bars.indexes}
    expected_indexes.update(
        constraint.name
        for constraint in daily_market_bars.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert reflected_indexes == expected_indexes
    with mssql_database.engine.connect() as connection:
        check_names = {
            str(row[0])
            for row in connection.exec_driver_sql(
                "SELECT cc.name FROM sys.check_constraints cc "
                "JOIN sys.tables t ON cc.parent_object_id = t.object_id "
                "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                "WHERE s.name = 'trading' AND t.name = 'daily_market_bars'"
            )
        }
    assert check_names == {
        constraint.name
        for constraint in daily_market_bars.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _invalid_rows() -> list[dict[str, object]]:
    valid = new_daily_market_bar_values(new_bar(command(201, 0), 201001))
    changes = (
        {"adjustment_basis": "UNKNOWN"},
        {"currency": "KRW"},
        {"observed_at": valid["available_at"], "available_at": valid["observed_at"]},
        {"high_price": 1},
        {"volume": -1},
        {"bar_key": "invalid"},
        {"content_digest": "g" * 64},
    )
    return [
        {**valid, **change, "daily_market_bar_id": UUID(int=201100 + index)}
        for index, change in enumerate(changes)
    ]


def test_representative_invalid_inserts_rollback_without_residue(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    invalid_rows = _invalid_rows()
    for row in invalid_rows:
        identifier = row["daily_market_bar_id"]
        with mssql_database.engine.connect() as connection:
            transaction = connection.begin()
            with pytest.raises(IntegrityError):
                connection.execute(daily_market_bars.insert().values(**row))
            transaction.rollback()
        with mssql_database.engine.connect() as connection:
            residue = connection.execute(
                select(daily_market_bars.c.daily_market_bar_id).where(
                    daily_market_bars.c.daily_market_bar_id == identifier
                )
            ).first()
        assert residue is None


@pytest.mark.parametrize("collision", ["semantic_identity", "session_revision"])
def test_semantic_and_session_revision_uniques_rollback_without_residue(
    mssql_database: TemporaryMssqlDatabase,
    collision: str,
) -> None:
    first = new_daily_market_bar_values(new_bar(command(202, 0), 202001))
    second = {
        **new_daily_market_bar_values(new_bar(command(202, 1), 202002)),
        "daily_market_bar_id": UUID(int=202002),
        "bar_key": "daily-market-bar:v1:" + "b" * 64,
    }
    if collision == "semantic_identity":
        for name in ("source_record_key", "source_version"):
            second[name] = first[name]
    else:
        for name in ("session_date", "available_at"):
            second[name] = first[name]
    with mssql_database.engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(daily_market_bars.insert().values(**first))
        with pytest.raises(IntegrityError):
            connection.execute(daily_market_bars.insert().values(**second))
        transaction.rollback()
    with mssql_database.engine.connect() as connection:
        count = connection.execute(
            select(daily_market_bars.c.daily_market_bar_id).where(
                daily_market_bars.c.daily_market_bar_id.in_(
                    [first["daily_market_bar_id"], second["daily_market_bar_id"]]
                )
            )
        ).all()
    assert count == []
