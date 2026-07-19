from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Unicode,
    Uuid,
    select,
)
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.dotnet.commands import (
    DotNetCommandExecutor,
    DotNetSqlParameter,
    DotNetSqlType,
)
from auto_trading_v2.adapters.persistence.dotnet.core_adapter import DotNetCoreConnection
from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    DotNetPersistenceError,
)
from auto_trading_v2.adapters.persistence.dotnet.results import DotNetRow, DotNetRows

metadata = MetaData()
sample = Table(
    "sample",
    metadata,
    Column("identifier", Uuid(), primary_key=True),
    Column("flag", Boolean(), nullable=False),
    Column("large", BigInteger(), nullable=False),
    Column("count", Integer(), nullable=False),
    Column("amount", Numeric(38, 18), nullable=False),
    Column("instant", DateTime(timezone=True), nullable=False),
    Column("day", Date(), nullable=False),
    Column("code", String(32), nullable=False),
    Column("details", Unicode(), nullable=False),
    schema="trading",
)


class CapturingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple[DotNetSqlParameter, ...], object]] = []

    def execute_non_query(
        self,
        connection: object,
        sql: str,
        parameters: tuple[DotNetSqlParameter, ...],
        *,
        transaction: object,
    ) -> int:
        self.calls.append(("non_query", sql, parameters, transaction))
        return 1

    def execute_rows(
        self,
        connection: object,
        sql: str,
        parameters: tuple[DotNetSqlParameter, ...],
        *,
        transaction: object,
    ) -> DotNetRows:
        self.calls.append(("rows", sql, parameters, transaction))
        row = DotNetRow(("identifier",), (UUID(int=1),))
        return DotNetRows(row.columns, (row,))


def _connection(executor: object) -> tuple[DotNetCoreConnection, object]:
    transaction = object()
    return (
        DotNetCoreConnection(
            object(),
            transaction,
            cast(DotNetCommandExecutor, executor),
        ),
        transaction,
    )


def test_insert_compiles_to_named_explicit_parameters_without_value_interpolation() -> None:
    executor = CapturingExecutor()
    connection, transaction = _connection(executor)
    sentinel = "runtime-value-must-not-appear-in-sql"
    identifier = UUID("12345678-1234-5678-1234-567812345678")

    result = connection.execute(
        sample.insert().values(
            identifier=identifier,
            flag=True,
            large=2**40,
            count=7,
            amount=Decimal("123.450000000000000000"),
            instant=datetime(2026, 7, 19, 1, 2, 3, 456789, tzinfo=UTC),
            day=date(2026, 7, 19),
            code="CODE",
            details=sentinel,
        )
    )

    kind, sql, parameters, captured_transaction = executor.calls[0]
    assert kind == "non_query"
    assert result.rowcount == 1
    assert captured_transaction is transaction
    assert sentinel not in sql
    assert "?" not in sql
    assert ":" not in sql
    assert all(parameter.name.startswith("@") for parameter in parameters)
    parameter_types = {parameter.name: parameter.sql_type for parameter in parameters}
    assert set(parameter_types.values()) == {
        DotNetSqlType.UNIQUEIDENTIFIER,
        DotNetSqlType.BIT,
        DotNetSqlType.BIGINT,
        DotNetSqlType.INTEGER,
        DotNetSqlType.DECIMAL,
        DotNetSqlType.DATETIMEOFFSET,
        DotNetSqlType.DATE,
        DotNetSqlType.VARCHAR,
        DotNetSqlType.NVARCHAR,
    }
    details = next(parameter for parameter in parameters if parameter.value == sentinel)
    assert details.size == -1


def test_select_result_supports_existing_repository_mapping_contract() -> None:
    executor = CapturingExecutor()
    connection, transaction = _connection(executor)

    result = connection.execute(
        select(sample.c.identifier).where(sample.c.identifier == UUID(int=1))
    )

    row = result.mappings().one_or_none()
    assert row is not None
    assert dict(row) == {"identifier": UUID(int=1)}
    kind, sql, parameters, captured_transaction = executor.calls[0]
    assert kind == "rows"
    assert "@identifier_1" in sql
    assert parameters[0].sql_type is DotNetSqlType.UNIQUEIDENTIFIER
    assert captured_transaction is transaction


def test_dotnet_constraint_failure_bridges_without_raw_provider_text() -> None:
    class FailingExecutor(CapturingExecutor):
        def execute_non_query(self, *args: Any, **kwargs: Any) -> int:
            raise DotNetPersistenceError(
                operation="execute_non_query",
                category=DotNetErrorCategory.UNIQUE_VIOLATION,
                number=2627,
                constraint="uq_safe_constraint",
            )

    connection, _ = _connection(FailingExecutor())

    with pytest.raises(IntegrityError) as caught:
        connection.execute(sample.insert().values(identifier=UUID(int=1)))

    rendered = str(caught.value)
    assert "UNIQUE_VIOLATION" in rendered
    assert "uq_safe_constraint" in rendered
    assert "server" not in rendered.casefold()
