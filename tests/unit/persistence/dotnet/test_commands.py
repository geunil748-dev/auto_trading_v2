from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from auto_trading_v2.adapters.persistence.dotnet.commands import (
    DotNetCommandExecutor,
    DotNetSqlParameter,
    DotNetSqlType,
)
from auto_trading_v2.adapters.persistence.dotnet.errors import DotNetParameterError
from auto_trading_v2.adapters.persistence.dotnet.runtime import DotNetBindings


class FakeSqlDbType:
    Bit = "Bit"
    BigInt = "BigInt"
    Int = "Int"
    NVarChar = "NVarChar"
    VarChar = "VarChar"
    UniqueIdentifier = "UniqueIdentifier"
    Decimal = "Decimal"
    DateTimeOffset = "DateTimeOffset"
    Date = "Date"


class FakeParameter:
    def __init__(self, name: str, sql_type: str) -> None:
        self.name = name
        self.sql_type = sql_type
        self.Size = None
        self.Precision = None
        self.Scale = None
        self.Value: object = None


class FakeParameters:
    def __init__(self) -> None:
        self.items: list[FakeParameter] = []

    def Add(self, name: str, sql_type: str) -> FakeParameter:
        parameter = FakeParameter(name, sql_type)
        self.items.append(parameter)
        return parameter


class FakeReader:
    def __init__(self) -> None:
        self.FieldCount = 2
        self._rows = [(1, "one"), (2, "two")]
        self._index = -1
        self.disposed = False

    def GetName(self, index: int) -> str:
        return ("number", "label")[index]

    def Read(self) -> bool:
        self._index += 1
        return self._index < len(self._rows)

    def GetValue(self, index: int) -> object:
        return self._rows[self._index][index]

    def Dispose(self) -> None:
        self.disposed = True


class FakeCommand:
    def __init__(self) -> None:
        self.CommandText = ""
        self.Transaction = None
        self.Parameters = FakeParameters()
        self.disposed = False
        self.reader = FakeReader()

    def ExecuteScalar(self) -> int:
        return 1

    def ExecuteNonQuery(self) -> int:
        return 3

    def ExecuteReader(self) -> FakeReader:
        return self.reader

    def Dispose(self) -> None:
        self.disposed = True


class FakeConnection:
    def __init__(self) -> None:
        self.commands: list[FakeCommand] = []

    def CreateCommand(self) -> FakeCommand:
        command = FakeCommand()
        self.commands.append(command)
        return command


class FakeDateTime:
    def __init__(self, *parts: object) -> None:
        self.parts = parts
        self.extra_ticks = 0

    def AddTicks(self, ticks: int) -> FakeDateTime:
        self.extra_ticks = ticks
        return self


class FakeDecimal:
    @staticmethod
    def Parse(value: str, culture: object) -> tuple[str, str, object]:
        return ("decimal", value, culture)


def _bindings() -> DotNetBindings:
    return cast(
        DotNetBindings,
        SimpleNamespace(
            sql_db_type=FakeSqlDbType,
            db_null=SimpleNamespace(Value="DBNULL"),
            net_boolean=lambda value: ("bool", value),
            net_int64=lambda value: ("int64", value),
            net_int32=lambda value: ("int32", value),
            net_guid=lambda value: ("guid", value),
            net_decimal=FakeDecimal,
            invariant_culture="invariant",
            net_date_time=FakeDateTime,
            net_date_time_kind=SimpleNamespace(Utc="Utc"),
            net_date_time_offset=lambda value: ("datetimeoffset", value),
        ),
    )


def test_all_supported_parameter_types_are_explicitly_bound() -> None:
    connection = FakeConnection()
    executor = DotNetCommandExecutor(_bindings)
    identifier = UUID("12345678-1234-5678-1234-567812345678")
    instant = datetime(2026, 7, 19, 1, 2, 3, 456789, tzinfo=UTC)
    parameters = (
        DotNetSqlParameter("flag", DotNetSqlType.BIT, True),
        DotNetSqlParameter("big", DotNetSqlType.BIGINT, 2**40),
        DotNetSqlParameter("small", DotNetSqlType.INTEGER, 7),
        DotNetSqlParameter("text", DotNetSqlType.NVARCHAR, "한글", size=20),
        DotNetSqlParameter("ascii", DotNetSqlType.VARCHAR, "USD", size=3),
        DotNetSqlParameter("identifier", DotNetSqlType.UNIQUEIDENTIFIER, identifier),
        DotNetSqlParameter(
            "amount",
            DotNetSqlType.DECIMAL,
            Decimal("123.450000000000000000"),
            precision=38,
            scale=18,
        ),
        DotNetSqlParameter("instant", DotNetSqlType.DATETIMEOFFSET, instant),
        DotNetSqlParameter("day", DotNetSqlType.DATE, date(2026, 7, 19)),
        DotNetSqlParameter("missing", DotNetSqlType.NVARCHAR, None, size=10),
    )
    sql = "SELECT " + ", ".join(parameter.name for parameter in parameters)

    assert executor.execute_scalar(connection, sql, parameters, transaction="tx") == 1

    command = connection.commands[0]
    assert command.Transaction == "tx"
    assert command.disposed is True
    assert [item.sql_type for item in command.Parameters.items] == [
        "Bit",
        "BigInt",
        "Int",
        "NVarChar",
        "VarChar",
        "UniqueIdentifier",
        "Decimal",
        "DateTimeOffset",
        "Date",
        "NVarChar",
    ]
    decimal_value = command.Parameters.items[6].Value
    assert decimal_value == ("decimal", "123.450000000000000000", "invariant")
    datetime_value: Any = command.Parameters.items[7].Value
    assert datetime_value[0] == "datetimeoffset"
    assert datetime_value[1].extra_ticks == 7890
    assert command.Parameters.items[-1].Value == "DBNULL"


def test_non_query_and_rows_dispose_all_resources() -> None:
    connection = FakeConnection()
    executor = DotNetCommandExecutor(_bindings)

    assert executor.execute_non_query(connection, "SELECT 1") == 3
    rows = executor.execute_rows(connection, "SELECT 1 AS number, 'one' AS label")

    assert rows.rowcount == 2
    assert rows[0]["number"] == 1
    assert rows[1].as_tuple() == (2, "two")
    assert connection.commands[0].disposed is True
    assert connection.commands[1].reader.disposed is True
    assert connection.commands[1].disposed is True


@pytest.mark.parametrize(
    "parameter",
    [
        lambda: DotNetSqlParameter("text", DotNetSqlType.NVARCHAR, "value"),
        lambda: DotNetSqlParameter("amount", DotNetSqlType.DECIMAL, Decimal("1")),
        lambda: DotNetSqlParameter(
            "instant",
            DotNetSqlType.DATETIMEOFFSET,
            datetime(2026, 1, 1),
        ),
        lambda: DotNetSqlParameter("bad name", DotNetSqlType.INTEGER, 1),
        lambda: DotNetSqlParameter("value", DotNetSqlType.BIGINT, True),
    ],
)
def test_invalid_parameter_shapes_fail_before_command_execution(parameter: object) -> None:
    with pytest.raises(DotNetParameterError):
        cast(Any, parameter)()


def test_positional_question_mark_parameters_are_rejected() -> None:
    executor = DotNetCommandExecutor(_bindings)
    with pytest.raises(DotNetParameterError):
        executor.execute_scalar(FakeConnection(), "SELECT ?")
