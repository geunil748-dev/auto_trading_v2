"""Compile SQLAlchemy Core statements without creating an online Engine."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.dialects import mssql
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.sql.elements import ClauseElement
from sqlalchemy.sql.sqltypes import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Unicode,
    Uuid,
)

from auto_trading_v2.adapters.persistence.dotnet.commands import (
    DotNetCommandExecutor,
    DotNetSqlParameter,
    DotNetSqlType,
)
from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    DotNetParameterError,
    DotNetPersistenceError,
    DotNetResultConversionError,
)
from auto_trading_v2.adapters.persistence.dotnet.results import DotNetRows

_BIND_PLACEHOLDER = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_DIALECT = mssql.dialect(paramstyle="named")  # type: ignore[no-untyped-call]


class _SafeDotNetOriginal(Exception):
    """Carry categorical bridge data without retaining provider text."""

    def __init__(self, error: DotNetPersistenceError) -> None:
        fragments = [error.category.value]
        if error.number is not None:
            fragments.append(str(error.number))
        constraint = getattr(error, "constraint", None)
        if constraint is not None:
            fragments.append(str(constraint))
        super().__init__(*fragments)


def _as_sqlalchemy_error(error: DotNetPersistenceError) -> SQLAlchemyError:
    original = _SafeDotNetOriginal(error)
    if error.category in {
        DotNetErrorCategory.UNIQUE_VIOLATION,
        DotNetErrorCategory.CONSTRAINT_VIOLATION,
        DotNetErrorCategory.FOREIGN_KEY_VIOLATION,
        DotNetErrorCategory.CHECK_CONSTRAINT_VIOLATION,
    }:
        return IntegrityError(None, None, original)
    invalidated = error.category in {
        DotNetErrorCategory.AUTHENTICATION,
        DotNetErrorCategory.CONNECTION_FAILURE,
        DotNetErrorCategory.DATABASE_UNAVAILABLE,
    }
    return DBAPIError(None, None, original, connection_invalidated=invalidated)


def _string_parameter(name: str, value: object, sql_type: object) -> DotNetSqlParameter:
    size = getattr(sql_type, "length", None)
    return DotNetSqlParameter(
        name,
        DotNetSqlType.NVARCHAR if isinstance(sql_type, Unicode) else DotNetSqlType.VARCHAR,
        value,
        size=-1 if size is None else int(size),
    )


def _parameter(name: str, value: object, sql_type: object) -> DotNetSqlParameter:
    if isinstance(sql_type, Uuid):
        return DotNetSqlParameter(name, DotNetSqlType.UNIQUEIDENTIFIER, value)
    if isinstance(sql_type, Boolean):
        return DotNetSqlParameter(name, DotNetSqlType.BIT, value)
    if isinstance(sql_type, BigInteger):
        return DotNetSqlParameter(name, DotNetSqlType.BIGINT, value)
    if isinstance(sql_type, Integer):
        return DotNetSqlParameter(name, DotNetSqlType.INTEGER, value)
    if isinstance(sql_type, Numeric):
        if sql_type.precision != 38 or sql_type.scale != 18:
            raise DotNetParameterError("numeric binds require DECIMAL(38,18)")
        return DotNetSqlParameter(
            name,
            DotNetSqlType.DECIMAL,
            value,
            precision=38,
            scale=18,
        )
    if isinstance(sql_type, DateTime):
        return DotNetSqlParameter(name, DotNetSqlType.DATETIMEOFFSET, value)
    if isinstance(sql_type, Date):
        return DotNetSqlParameter(name, DotNetSqlType.DATE, value)
    if isinstance(sql_type, String):
        return _string_parameter(name, value, sql_type)
    raise DotNetParameterError("unsupported SQLAlchemy Core bind type")


def _compile(statement: ClauseElement) -> tuple[str, tuple[DotNetSqlParameter, ...]]:
    compiled: Any = statement.compile(
        dialect=_DIALECT,
        compile_kwargs={"render_postcompile": True},
    )
    if not any(
        bool(getattr(statement, attribute, False))
        for attribute in ("is_select", "is_insert", "is_update")
    ):
        raise DotNetParameterError("only SELECT, INSERT, and UPDATE Core statements are allowed")
    names: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        names.add(match.group(1))
        return f"@{match.group(1)}"

    sql = _BIND_PLACEHOLDER.sub(replace, str(compiled))
    params = compiled.params
    if names != set(params):
        raise DotNetParameterError("compiled parameter contract mismatch")
    parameters = tuple(
        _parameter(f"@{name}", value, compiled.binds[name].type) for name, value in params.items()
    )
    return sql, parameters


@dataclass(frozen=True, slots=True)
class DotNetCoreResult:
    rows: DotNetRows | None
    rowcount: int

    def mappings(self) -> DotNetCoreResult:
        return self

    def all(self) -> Sequence[Mapping[str, object]]:
        return () if self.rows is None else self.rows.rows

    def one_or_none(self) -> Mapping[str, object] | None:
        if self.rows is None or len(self.rows) == 0:
            return None
        if len(self.rows) != 1:
            raise SQLAlchemyError("DotNet result cardinality mismatch")
        return self.rows[0]


@dataclass(slots=True, repr=False)
class DotNetCoreConnection:
    """Connection.execute-compatible compiler boundary for existing repositories."""

    connection: object
    transaction: object
    executor: DotNetCommandExecutor

    def execute(self, statement: ClauseElement) -> DotNetCoreResult:
        try:
            sql, parameters = _compile(statement)
            if bool(getattr(statement, "is_select", False)):
                rows = self.executor.execute_rows(
                    self.connection,
                    sql,
                    parameters,
                    transaction=self.transaction,
                )
                return DotNetCoreResult(rows, len(rows))
            rowcount = self.executor.execute_non_query(
                self.connection,
                sql,
                parameters,
                transaction=self.transaction,
            )
            return DotNetCoreResult(None, rowcount)
        except DotNetPersistenceError as exc:
            raise _as_sqlalchemy_error(exc) from None
        except (DotNetParameterError, DotNetResultConversionError, ValueError):
            raise SQLAlchemyError("DotNet Core execution failed safely") from None


__all__ = ["DotNetCoreConnection", "DotNetCoreResult"]
