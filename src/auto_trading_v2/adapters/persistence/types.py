"""MSSQL type, collation, default, and check-expression policy."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, text
from sqlalchemy.dialects import mssql
from sqlalchemy.sql.elements import TextClause

DECIMAL_PRECISION = 38
DECIMAL_SCALE = 18
BINARY_COLLATION = "Latin1_General_100_BIN2"


def uuid_type() -> mssql.UNIQUEIDENTIFIER[UUID]:
    """Return the UUID storage type without a database-side ID default."""

    return mssql.UNIQUEIDENTIFIER(as_uuid=True)


def decimal_type() -> Numeric[Decimal]:
    """Return the canonical fixed-precision Decimal storage type."""

    return mssql.DECIMAL(DECIMAL_PRECISION, DECIMAL_SCALE, asdecimal=True)


def timestamp_type() -> mssql.DATETIMEOFFSET:
    """Return the canonical timezone-aware timestamp type."""

    return mssql.DATETIMEOFFSET(precision=7)  # type: ignore[no-untyped-call]


def json_text_type() -> mssql.NVARCHAR:
    """Return SQL Server's unbounded Unicode JSON text storage type."""

    return mssql.NVARCHAR(length=None)


def symbol_type() -> mssql.VARCHAR:
    """Return storage matching the domain Symbol maximum length."""

    return mssql.VARCHAR(32, collation=BINARY_COLLATION)


def currency_type() -> mssql.CHAR:
    """Return deterministic three-letter ASCII currency storage."""

    return mssql.CHAR(3, collation=BINARY_COLLATION)


def code_type(length: int) -> mssql.VARCHAR:
    """Return binary-collated ASCII technical-key storage."""

    return mssql.VARCHAR(length, collation=BINARY_COLLATION)


def utc_server_default() -> TextClause:
    """Return a server expression with an explicit UTC offset."""

    return text("TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00')")


def symbol_check_sql(column: str = "symbol") -> str:
    """Mirror the domain pattern ``[A-Z0-9][A-Z0-9.-]{0,31}``."""

    return (
        f"DATALENGTH({column}) BETWEEN 1 AND 32 "
        f"AND LEFT({column}, 1) COLLATE {BINARY_COLLATION} LIKE '[A-Z0-9]' "
        f"AND {column} COLLATE {BINARY_COLLATION} NOT LIKE '%[^A-Z0-9.-]%'"
    )


def currency_check_sql(column: str = "currency") -> str:
    """Require exactly three uppercase ASCII letters."""

    return f"DATALENGTH({column}) = 3 AND {column} COLLATE {BINARY_COLLATION} NOT LIKE '%[^A-Z]%'"


def json_object_check_sql(column: str) -> str:
    """Require valid JSON whose first non-space token is an object."""

    return f"ISJSON({column}) = 1 AND LEFT(LTRIM({column}), 1) = '{{'"


def json_array_check_sql(column: str) -> str:
    """Require valid JSON whose first non-space token is an array."""

    return f"ISJSON({column}) = 1 AND LEFT(LTRIM({column}), 1) = '['"


def non_empty_check_sql(column: str) -> str:
    """Reject empty and whitespace-only technical keys."""

    return f"DATALENGTH(LTRIM(RTRIM({column}))) > 0"
