"""Frozen MSSQL type and SQL-expression policy for revision 0001."""

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.sql.elements import conv

SCHEMA = "trading"
COLLATION = "Latin1_General_100_BIN2"
UTC_DEFAULT = sa.text("TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00')")


def named_check_constraint(sqltext: str, *, name: str) -> sa.CheckConstraint:
    """Preserve a frozen migration constraint name under naming conventions."""

    return sa.CheckConstraint(sqltext, name=conv(name))


def uuid_type() -> mssql.UNIQUEIDENTIFIER:
    return mssql.UNIQUEIDENTIFIER(as_uuid=True)


def decimal_type() -> sa.Numeric:
    return mssql.DECIMAL(38, 18, asdecimal=True)


def timestamp_type() -> mssql.DATETIMEOFFSET:
    return mssql.DATETIMEOFFSET(precision=7)


def json_type() -> mssql.NVARCHAR:
    return mssql.NVARCHAR(length=None)


def code_type(length: int) -> mssql.VARCHAR:
    return mssql.VARCHAR(length, collation=COLLATION)


def symbol_type() -> mssql.VARCHAR:
    return code_type(32)


def currency_type() -> mssql.CHAR:
    return mssql.CHAR(3, collation=COLLATION)


def symbol_check(column: str = "symbol") -> str:
    return (
        f"DATALENGTH({column}) BETWEEN 1 AND 32 "
        f"AND LEFT({column}, 1) COLLATE {COLLATION} LIKE '[A-Z0-9]' "
        f"AND {column} COLLATE {COLLATION} NOT LIKE '%[^A-Z0-9.-]%'"
    )


def currency_check(column: str = "currency") -> str:
    return f"DATALENGTH({column}) = 3 AND {column} COLLATE {COLLATION} NOT LIKE '%[^A-Z]%'"


def json_object_check(column: str) -> str:
    return f"ISJSON({column}) = 1 AND LEFT(LTRIM({column}), 1) = '{{'"


def json_array_check(column: str) -> str:
    return f"ISJSON({column}) = 1 AND LEFT(LTRIM({column}), 1) = '['"
