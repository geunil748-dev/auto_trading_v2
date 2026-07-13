"""Credential-safe SQLAlchemy URL and engine construction helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Self

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

ADMIN_URL_ENV = "AUTO_TRADING_V2_MSSQL_ADMIN_URL"
DATABASE_URL_ENV = "AUTO_TRADING_V2_DATABASE_URL"
TEST_ADMIN_URL_ENV = "AUTO_TRADING_V2_TEST_ADMIN_URL"
ALLOWED_URL_ENVIRONMENTS = frozenset({ADMIN_URL_ENV, DATABASE_URL_ENV, TEST_ADMIN_URL_ENV})

_DATABASE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


class DatabaseConfigurationError(RuntimeError):
    """Raised when V2 MSSQL configuration is absent or unsafe."""


def _single_query_value(value: str | tuple[str, ...] | None) -> str | None:
    """Return one URL query value and reject ambiguous repeated values."""

    if isinstance(value, tuple):
        raise DatabaseConfigurationError("ODBC driver query 값은 하나만 허용합니다.")
    return value


def validate_database_identifier(database_name: str) -> str:
    """Validate a SQL Server database identifier before interpolation."""

    if not isinstance(database_name, str) or not _DATABASE_IDENTIFIER.fullmatch(database_name):
        raise DatabaseConfigurationError("유효하지 않은 database 이름입니다.")
    return database_name


def quote_database_identifier(database_name: str) -> str:
    """Quote a previously validated SQL Server database identifier."""

    return f"[{validate_database_identifier(database_name)}]"


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseUrl:
    """Hold a validated MSSQL URL while redacting its string representations."""

    _value: str

    def __post_init__(self) -> None:
        try:
            parsed = make_url(self._value)
        except (ArgumentError, TypeError, ValueError) as exc:
            raise DatabaseConfigurationError("유효한 SQLAlchemy URL이 아닙니다.") from exc
        if parsed.drivername != "mssql+pyodbc":
            raise DatabaseConfigurationError("mssql+pyodbc URL만 허용합니다.")
        configured_driver = _single_query_value(parsed.query.get("driver"))
        if configured_driver and "freetds" in configured_driver.casefold():
            raise DatabaseConfigurationError("FreeTDS driver는 허용하지 않습니다.")

    @classmethod
    def from_environment(cls, variable_name: str) -> Self:
        """Read only one of the explicitly approved V2 environment variables."""

        if variable_name not in ALLOWED_URL_ENVIRONMENTS:
            raise DatabaseConfigurationError("허용되지 않은 환경 변수 이름입니다.")
        value = os.environ.get(variable_name)
        if not value:
            raise DatabaseConfigurationError(f"{variable_name} 환경 변수가 필요합니다.")
        return cls(value)

    @property
    def sqlalchemy_url(self) -> URL:
        """Return SQLAlchemy's immutable URL object for engine construction."""

        return make_url(self._value)

    @property
    def database_name(self) -> str | None:
        """Return the configured database name without other connection details."""

        return self.sqlalchemy_url.database

    @property
    def driver_name(self) -> str | None:
        """Return the configured ODBC driver name, if the URL declares one."""

        return _single_query_value(self.sqlalchemy_url.query.get("driver"))

    def for_database(self, database_name: str) -> Self:
        """Return a new protected URL targeting a validated database name."""

        validated = validate_database_identifier(database_name)
        target = self.sqlalchemy_url.set(database=validated)
        return type(self)(target.render_as_string(hide_password=False))

    def require_database(self, expected_name: str) -> Self:
        """Require the URL to target exactly the expected database."""

        if self.database_name != expected_name:
            raise DatabaseConfigurationError(f"database 이름은 {expected_name}이어야 합니다.")
        return self

    def __repr__(self) -> str:
        return "DatabaseUrl(<redacted>)"

    def __str__(self) -> str:
        return "<redacted-mssql-url>"


def create_database_engine(settings: DatabaseUrl, *, autocommit: bool = False) -> Engine:
    """Create an engine without opening a connection or mutating database state."""

    options: dict[str, object] = {"pool_pre_ping": True}
    if autocommit:
        options["isolation_level"] = "AUTOCOMMIT"
    return create_engine(settings.sqlalchemy_url, **options)
