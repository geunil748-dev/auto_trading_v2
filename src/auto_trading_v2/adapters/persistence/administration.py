"""Explicit MSSQL administration engines with a guarded local LPC option."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pyodbc  # type: ignore[import-not-found]
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from auto_trading_v2.adapters.persistence.database import (
    DatabaseConfigurationError,
    DatabaseUrl,
)
from auto_trading_v2.adapters.persistence.database_admin import (
    validate_test_database_name,
)
from auto_trading_v2.config import (
    MssqlAdministrationSettings,
    MssqlAdministrationTransport,
)

_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
_LOCAL_SERVER = "lpc:(local)"
_CONNECT_TIMEOUT_SECONDS = 5


class MssqlAdministrationErrorCategory(StrEnum):
    """Value-free categories for unsafe administration configuration or connections."""

    URL_NOT_CONFIGURED = "MSSQL_ADMIN_URL_NOT_CONFIGURED"
    LPC_URL_INVALID = "MSSQL_LPC_URL_INVALID"
    LPC_DATABASE_NOT_MASTER = "MSSQL_LPC_DATABASE_NOT_MASTER"
    LPC_REMOTE_ENDPOINT = "MSSQL_LPC_REMOTE_ENDPOINT"
    LPC_NAMED_INSTANCE_UNVERIFIED = "MSSQL_LPC_NAMED_INSTANCE_UNVERIFIED"
    LPC_CREDENTIALS_PRESENT = "MSSQL_LPC_CREDENTIALS_PRESENT"
    LPC_DRIVER_UNSUPPORTED = "MSSQL_LPC_DRIVER_UNSUPPORTED"
    LPC_QUERY_AMBIGUOUS = "MSSQL_LPC_QUERY_AMBIGUOUS"
    LPC_INTEGRATED_AUTH_REQUIRED = "MSSQL_LPC_INTEGRATED_AUTH_REQUIRED"
    LPC_SQL_AUTH_MIXED = "MSSQL_LPC_SQL_AUTH_MIXED"
    LPC_DSN_UNSUPPORTED = "MSSQL_LPC_DSN_UNSUPPORTED"
    LPC_CONNECTION_FAILED = "MSSQL_LPC_CONNECTION_FAILED"
    LPC_DATABASE_MISMATCH = "MSSQL_LPC_DATABASE_MISMATCH"
    LPC_TRANSPORT_MISMATCH = "MSSQL_LPC_TRANSPORT_MISMATCH"
    LPC_AUTH_MISMATCH = "MSSQL_LPC_AUTH_MISMATCH"
    LPC_PERMISSION_INSUFFICIENT = "MSSQL_LPC_PERMISSION_INSUFFICIENT"


class MssqlAdministrationSafetyError(DatabaseConfigurationError):
    """Reject an unsafe administration path without retaining its raw value."""

    def __init__(self, category: MssqlAdministrationErrorCategory) -> None:
        self.category = category
        super().__init__(category.value)


@dataclass(frozen=True, slots=True)
class LocalSharedMemoryConnectionInfo:
    """Safe connection facts that contain no principal or endpoint identity."""

    database_matches: bool
    shared_memory: bool
    integrated_auth: bool
    auth_scheme: str
    can_create_database: bool
    can_alter_database: bool


def _normalized_query(query: Mapping[str, str | tuple[str, ...]]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in query.items():
        key = "".join(character for character in str(raw_key).casefold() if character.isalnum())
        if isinstance(raw_value, tuple) or key in normalized:
            raise MssqlAdministrationSafetyError(
                MssqlAdministrationErrorCategory.LPC_QUERY_AMBIGUOUS
            )
        normalized[key] = str(raw_value)
    return normalized


def _is_local_endpoint(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().casefold()
    if normalized in {"localhost", "(local)", "."}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_enabled(value: str | None) -> bool:
    return value is not None and value.strip().casefold() in {"1", "true", "yes", "on", "sspi"}


def _validate_local_shared_memory_url(settings: MssqlAdministrationSettings) -> None:
    protected = settings.selected_admin_url
    if protected is None:
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.URL_NOT_CONFIGURED)
    try:
        parsed = DatabaseUrl(protected.reveal()).sqlalchemy_url
    except DatabaseConfigurationError:
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_URL_INVALID
        ) from None

    if parsed.database != "master":
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_DATABASE_NOT_MASTER
        )
    if parsed.username not in {None, ""} or parsed.password not in {None, ""}:
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_CREDENTIALS_PRESENT
        )
    if parsed.host and ("\\" in parsed.host or "/" in parsed.host):
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_NAMED_INSTANCE_UNVERIFIED
        )
    if not _is_local_endpoint(parsed.host):
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.LPC_REMOTE_ENDPOINT)

    query = _normalized_query(parsed.query)
    driver = query.get("driver")
    if driver is None or driver.strip().casefold() != _ODBC_DRIVER.casefold():
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_DRIVER_UNSUPPORTED
        )
    if {"dsn", "odbcconnect"} & query.keys():
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.LPC_DSN_UNSUPPORTED)
    if {
        "uid",
        "pwd",
        "user",
        "username",
        "password",
        "authentication",
        "address",
        "network",
        "serverspn",
    } & query.keys():
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.LPC_SQL_AUTH_MIXED)

    trusted = _is_enabled(query.get("trustedconnection"))
    integrated = _is_enabled(query.get("integratedsecurity"))
    if trusted and integrated:
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.LPC_QUERY_AMBIGUOUS)
    if not trusted and not integrated:
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_INTEGRATED_AUTH_REQUIRED
        )


def _local_shared_memory_engine(database_name: str, *, autocommit: bool) -> Engine:
    connection_string = ";".join(
        (
            f"DRIVER={{{_ODBC_DRIVER}}}",
            f"SERVER={_LOCAL_SERVER}",
            f"DATABASE={database_name}",
            "Trusted_Connection=yes",
            "Encrypt=no",
            "TrustServerCertificate=yes",
            f"Connection Timeout={_CONNECT_TIMEOUT_SECONDS}",
            "APP=auto_trading_v2_local_test_administration",
        )
    )

    def connect() -> Any:
        try:
            return pyodbc.connect(connection_string, autocommit=autocommit)
        except pyodbc.Error:
            raise MssqlAdministrationSafetyError(
                MssqlAdministrationErrorCategory.LPC_CONNECTION_FAILED
            ) from None

    options: dict[str, object] = {
        "creator": connect,
        "echo": False,
        "hide_parameters": True,
        "poolclass": NullPool,
    }
    if autocommit:
        options["isolation_level"] = "AUTOCOMMIT"
    return create_engine(URL.create("mssql+pyodbc"), **options)


@dataclass(frozen=True, slots=True, repr=False)
class MssqlAdministrationEngineFactory:
    """Create one explicitly selected TCP or local shared-memory engine path."""

    settings: MssqlAdministrationSettings = field(repr=False)

    def create_master_engine(self) -> Engine:
        """Create an unconnected autocommit engine for the master database."""

        return self._create_engine("master", autocommit=True)

    def create_target_engine(self, database_name: str) -> Engine:
        """Create an unconnected transactional engine for one guarded test database."""

        validated = validate_test_database_name(database_name)
        return self._create_engine(validated, autocommit=False)

    def _create_engine(self, database_name: str, *, autocommit: bool) -> Engine:
        transport = self.settings.selected_admin_transport
        protected = self.settings.selected_admin_url
        if protected is None:
            raise MssqlAdministrationSafetyError(
                MssqlAdministrationErrorCategory.URL_NOT_CONFIGURED
            )
        if transport is MssqlAdministrationTransport.TCP_URL:
            master = DatabaseUrl(protected.reveal()).require_database("master")
            selected = master if database_name == "master" else master.for_database(database_name)
            from auto_trading_v2.adapters.persistence.database import create_database_engine

            return create_database_engine(selected, autocommit=autocommit)
        if transport is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY:
            _validate_local_shared_memory_url(self.settings)
            return _local_shared_memory_engine(database_name, autocommit=autocommit)
        raise AssertionError("unreachable MSSQL administration transport")


def verify_local_shared_memory_connection(
    connection: Connection,
    *,
    expected_database: str,
    require_admin_permissions: bool,
) -> LocalSharedMemoryConnectionInfo:
    """Verify the connected LPC target using value-free result metadata."""

    row = (
        connection.exec_driver_sql(
            "SELECT CAST(DB_NAME() AS nvarchar(128)) AS database_name, "
            "CAST(CONNECTIONPROPERTY('net_transport') AS nvarchar(40)) AS net_transport, "
            "CAST(CONNECTIONPROPERTY('auth_scheme') AS nvarchar(40)) AS auth_scheme, "
            "CAST(HAS_PERMS_BY_NAME(NULL, NULL, 'CREATE ANY DATABASE') AS int) "
            "AS can_create_database, "
            "CAST(HAS_PERMS_BY_NAME(NULL, NULL, 'ALTER ANY DATABASE') AS int) "
            "AS can_alter_database"
        )
        .mappings()
        .one()
    )
    database_matches = str(row["database_name"]) == expected_database
    shared_memory = str(row["net_transport"]).strip().casefold() == "shared memory"
    auth_scheme = str(row["auth_scheme"]).strip().upper()
    integrated_auth = auth_scheme in {"NTLM", "KERBEROS"}
    can_create = bool(row["can_create_database"])
    can_alter = bool(row["can_alter_database"])
    if not database_matches:
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.LPC_DATABASE_MISMATCH)
    if not shared_memory:
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_TRANSPORT_MISMATCH
        )
    if not integrated_auth:
        raise MssqlAdministrationSafetyError(MssqlAdministrationErrorCategory.LPC_AUTH_MISMATCH)
    if require_admin_permissions and (not can_create or not can_alter):
        raise MssqlAdministrationSafetyError(
            MssqlAdministrationErrorCategory.LPC_PERMISSION_INSUFFICIENT
        )
    return LocalSharedMemoryConnectionInfo(
        database_matches=True,
        shared_memory=True,
        integrated_auth=True,
        auth_scheme=auth_scheme,
        can_create_database=can_create,
        can_alter_database=can_alter,
    )
