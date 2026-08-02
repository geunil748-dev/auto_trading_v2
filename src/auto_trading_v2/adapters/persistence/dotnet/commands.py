"""Explicitly typed, parameterized System.Data.SqlClient command executor."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetParameterError,
    safe_persistence_error,
)
from auto_trading_v2.adapters.persistence.dotnet.results import (
    DotNetRow,
    DotNetRows,
    convert_dotnet_value,
)
from auto_trading_v2.adapters.persistence.dotnet.runtime import (
    DotNetBindings,
    get_sqlclient_bindings,
)

_PARAMETER_NAME = re.compile(r"^@[A-Za-z_][A-Za-z0-9_]*$")


def validate_decimal_shape(precision: object, scale: object) -> tuple[int, int]:
    """Validate an explicit SQL Server DECIMAL shape without inspecting values."""

    if precision is None:
        raise DotNetParameterError("DECIMAL_PRECISION_REQUIRED")
    if not isinstance(precision, int) or isinstance(precision, bool):
        raise DotNetParameterError("DECIMAL_PRECISION_INVALID")
    if not 1 <= precision <= 38:
        raise DotNetParameterError("DECIMAL_PRECISION_OUT_OF_RANGE")
    if scale is None:
        raise DotNetParameterError("DECIMAL_SCALE_REQUIRED")
    if not isinstance(scale, int) or isinstance(scale, bool):
        raise DotNetParameterError("DECIMAL_SCALE_INVALID")
    if not 0 <= scale <= precision:
        raise DotNetParameterError("DECIMAL_SCALE_OUT_OF_RANGE")
    return precision, scale


class DotNetSqlType(StrEnum):
    BIT = "Bit"
    BIGINT = "BigInt"
    INTEGER = "Int"
    NVARCHAR = "NVarChar"
    VARCHAR = "VarChar"
    UNIQUEIDENTIFIER = "UniqueIdentifier"
    DECIMAL = "Decimal"
    DATETIMEOFFSET = "DateTimeOffset"
    DATE = "Date"


@dataclass(frozen=True, slots=True)
class DotNetSqlParameter:
    name: str
    sql_type: DotNetSqlType
    value: object
    size: int | None = None
    precision: int | None = None
    scale: int | None = None

    def __post_init__(self) -> None:
        normalized = self.name if self.name.startswith("@") else f"@{self.name}"
        if not _PARAMETER_NAME.fullmatch(normalized):
            raise DotNetParameterError("invalid parameter name")
        object.__setattr__(self, "name", normalized)
        self._validate_shape()

    def _validate_shape(self) -> None:
        if self.sql_type in {DotNetSqlType.NVARCHAR, DotNetSqlType.VARCHAR}:
            if self.size is None or self.size == 0 or self.size < -1:
                raise DotNetParameterError("string parameters require an explicit size")
        elif self.size is not None:
            raise DotNetParameterError("size is supported only for string parameters")
        if self.sql_type is DotNetSqlType.DECIMAL:
            validate_decimal_shape(self.precision, self.scale)
        elif self.precision is not None or self.scale is not None:
            raise DotNetParameterError("precision and scale are supported only for decimal")
        _validate_python_value(self.sql_type, self.value)


def _validate_python_value(sql_type: DotNetSqlType, value: object) -> None:
    if value is None:
        return
    if sql_type is DotNetSqlType.BIT:
        accepted = isinstance(value, bool)
    elif sql_type in {DotNetSqlType.BIGINT, DotNetSqlType.INTEGER}:
        accepted = isinstance(value, int) and not isinstance(value, bool)
    elif sql_type in {DotNetSqlType.NVARCHAR, DotNetSqlType.VARCHAR}:
        accepted = isinstance(value, str)
    elif sql_type is DotNetSqlType.UNIQUEIDENTIFIER:
        accepted = isinstance(value, UUID)
    elif sql_type is DotNetSqlType.DECIMAL:
        accepted = isinstance(value, Decimal) and value.is_finite()
    elif sql_type is DotNetSqlType.DATETIMEOFFSET:
        accepted = isinstance(value, datetime) and value.tzinfo is not None
    else:
        accepted = isinstance(value, date) and not isinstance(value, datetime)
    if not accepted:
        raise DotNetParameterError("parameter value does not match its explicit SQL type")


def _convert_parameter_value(
    specification: DotNetSqlParameter,
    bindings: DotNetBindings,
) -> object:
    value = specification.value
    if value is None:
        return bindings.db_null.Value
    if specification.sql_type is DotNetSqlType.BIT:
        return bindings.net_boolean(value)
    if specification.sql_type is DotNetSqlType.BIGINT:
        return bindings.net_int64(value)
    if specification.sql_type is DotNetSqlType.INTEGER:
        return bindings.net_int32(value)
    if specification.sql_type in {DotNetSqlType.NVARCHAR, DotNetSqlType.VARCHAR}:
        return value
    if specification.sql_type is DotNetSqlType.UNIQUEIDENTIFIER:
        return bindings.net_guid(str(value))
    if specification.sql_type is DotNetSqlType.DECIMAL:
        assert isinstance(value, Decimal)
        return bindings.net_decimal.Parse(format(value, "f"), bindings.invariant_culture)
    if specification.sql_type is DotNetSqlType.DATETIMEOFFSET:
        assert isinstance(value, datetime)
        utc = value.astimezone(UTC)
        net_datetime = bindings.net_date_time(
            utc.year,
            utc.month,
            utc.day,
            utc.hour,
            utc.minute,
            utc.second,
            utc.microsecond // 1000,
            bindings.net_date_time_kind.Utc,
        )
        net_datetime = net_datetime.AddTicks((utc.microsecond % 1000) * 10)
        return bindings.net_date_time_offset(net_datetime)
    if specification.sql_type is DotNetSqlType.DATE:
        assert isinstance(value, date)
        return bindings.net_date_time(value.year, value.month, value.day)
    raise DotNetParameterError("unsupported explicit SQL type")


@dataclass(slots=True, repr=False)
class DotNetCommandExecutor:
    bindings_provider: Callable[[], DotNetBindings] = get_sqlclient_bindings

    def _prepare_command(
        self,
        connection: object,
        sql: str,
        parameters: Sequence[DotNetSqlParameter],
        transaction: object | None,
    ) -> tuple[Any, DotNetBindings]:
        if not isinstance(sql, str) or not sql.strip():
            raise DotNetParameterError("SQL command text must not be empty")
        if "?" in sql:
            raise DotNetParameterError("positional question-mark parameters are not allowed")
        bindings = self.bindings_provider()
        dynamic_connection: Any = connection
        command: Any = dynamic_connection.CreateCommand()
        command.CommandText = sql
        if transaction is not None:
            command.Transaction = transaction
        try:
            for specification in parameters:
                if specification.name not in sql:
                    raise DotNetParameterError("SQL is missing an explicit named parameter")
                sql_db_type = getattr(bindings.sql_db_type, specification.sql_type.value)
                parameter: Any = command.Parameters.Add(specification.name, sql_db_type)
                if specification.size is not None:
                    parameter.Size = specification.size
                if specification.precision is not None:
                    parameter.Precision = specification.precision
                if specification.scale is not None:
                    parameter.Scale = specification.scale
                parameter.Value = _convert_parameter_value(specification, bindings)
        except DotNetParameterError:
            command.Dispose()
            raise
        except Exception as exc:
            command.Dispose()
            raise safe_persistence_error(exc, operation="prepare_command") from None
        return command, bindings

    def execute_scalar(
        self,
        connection: object,
        sql: str,
        parameters: Sequence[DotNetSqlParameter] = (),
        *,
        transaction: object | None = None,
    ) -> object:
        command, bindings = self._prepare_command(connection, sql, parameters, transaction)
        try:
            return convert_dotnet_value(command.ExecuteScalar(), bindings=bindings)
        except DotNetParameterError:
            raise
        except Exception as exc:
            raise safe_persistence_error(exc, operation="execute_scalar") from None
        finally:
            command.Dispose()

    def execute_non_query(
        self,
        connection: object,
        sql: str,
        parameters: Sequence[DotNetSqlParameter] = (),
        *,
        transaction: object | None = None,
    ) -> int:
        command, _ = self._prepare_command(connection, sql, parameters, transaction)
        try:
            return int(command.ExecuteNonQuery())
        except Exception as exc:
            raise safe_persistence_error(exc, operation="execute_non_query") from None
        finally:
            command.Dispose()

    def execute_rows(
        self,
        connection: object,
        sql: str,
        parameters: Sequence[DotNetSqlParameter] = (),
        *,
        transaction: object | None = None,
    ) -> DotNetRows:
        command, bindings = self._prepare_command(connection, sql, parameters, transaction)
        reader: Any | None = None
        try:
            reader = command.ExecuteReader()
            columns = tuple(str(reader.GetName(index)) for index in range(int(reader.FieldCount)))
            data_types = tuple(
                str(reader.GetDataTypeName(index)) if hasattr(reader, "GetDataTypeName") else ""
                for index in range(int(reader.FieldCount))
            )
            folded = tuple(column.casefold() for column in columns)
            if len(set(folded)) != len(folded):
                raise ValueError("duplicate result column names are not allowed")
            rows: list[DotNetRow] = []
            while bool(reader.Read()):
                values = tuple(
                    convert_dotnet_value(
                        reader.GetValue(index),
                        bindings=bindings,
                        data_type_name=data_types[index],
                    )
                    for index in range(len(columns))
                )
                rows.append(DotNetRow(columns, values))
            return DotNetRows(columns, tuple(rows))
        except ValueError:
            raise
        except Exception as exc:
            raise safe_persistence_error(exc, operation="execute_rows") from None
        finally:
            if reader is not None:
                reader.Dispose()
            command.Dispose()
