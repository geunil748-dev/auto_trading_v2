"""Explicit local-only settings for the V2 DotNet persistence provider."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from auto_trading_v2.config.errors import InvalidSettingError, MissingSettingError
from auto_trading_v2.config.loader import (
    DB_PROVIDER_KEY,
    ENVIRONMENT_KEY,
    MSSQL_CONNECT_TIMEOUT_KEY,
    MSSQL_DATABASE_KEY,
    MSSQL_ENCRYPT_KEY,
    MSSQL_HOST_KEY,
    MSSQL_PASSWORD_KEY,
    MSSQL_PORT_KEY,
    MSSQL_TRUST_CERTIFICATE_KEY,
    MSSQL_USERNAME_KEY,
    _read_env_file,
    _select_env_file,
)
from auto_trading_v2.config.models import DatabaseProvider, SecretValue
from auto_trading_v2.config.validation import normalize_choice, parse_boolean, require_text

DOTNET_DATABASE_KEYS = (
    DB_PROVIDER_KEY,
    MSSQL_HOST_KEY,
    MSSQL_PORT_KEY,
    MSSQL_DATABASE_KEY,
    MSSQL_USERNAME_KEY,
    MSSQL_PASSWORD_KEY,
    MSSQL_ENCRYPT_KEY,
    MSSQL_TRUST_CERTIFICATE_KEY,
    MSSQL_CONNECT_TIMEOUT_KEY,
    ENVIRONMENT_KEY,
)


@dataclass(frozen=True, slots=True)
class DotNetDatabaseInventory:
    """Value-free readiness counts for the explicit DotNet settings."""

    configured_count: int
    missing_count: int


@dataclass(frozen=True, slots=True, repr=False)
class DotNetDatabaseSettings:
    """Validated settings whose representation omits endpoint and credentials."""

    provider: DatabaseProvider
    environment: str
    host: str
    port: int
    database: str
    username: SecretValue
    password: SecretValue
    encrypt: bool
    trust_server_certificate: bool
    connect_timeout: int

    @property
    def data_source(self) -> str:
        """Return the validated local TCP data source for SqlClient only."""

        rendered_host = f"[{self.host}]" if ":" in self.host else self.host
        return f"tcp:{rendered_host},{self.port}"

    def __repr__(self) -> str:
        return (
            "DotNetDatabaseSettings(provider='dotnet', endpoint=<local>, "
            "database=<v2>, username=<redacted>, password=<redacted>, "
            f"environment={self.environment!r}, encrypt={self.encrypt!r}, "
            f"trust_server_certificate={self.trust_server_certificate!r}, "
            f"connect_timeout={self.connect_timeout!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def _resolved_values(
    env_file: Path | None,
    environ: Mapping[str, str] | None,
    process_environ: Mapping[str, str] | None,
) -> dict[str, str | None]:
    selected = _select_env_file(env_file)
    dotenv = _read_env_file(selected)
    explicit = {} if environ is None else environ
    process = os.environ if process_environ is None else process_environ
    resolved: dict[str, str | None] = {}
    for key in DOTNET_DATABASE_KEYS:
        if key in explicit:
            resolved[key] = explicit[key]
        elif key in dotenv:
            resolved[key] = dotenv[key]
        else:
            resolved[key] = process.get(key)
    return resolved


def inspect_dotnet_database_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> DotNetDatabaseInventory:
    """Return configured/missing counts without retaining names or values."""

    values = _resolved_values(env_file, environ, process_environ)
    configured = sum(bool(value and value.strip()) for value in values.values())
    return DotNetDatabaseInventory(configured, len(DOTNET_DATABASE_KEYS) - configured)


def _required(values: Mapping[str, str | None], key: str) -> str:
    value = values.get(key)
    if value is None or not value.strip():
        raise MissingSettingError(key)
    return value.strip()


def _parse_bounded_integer(
    key: str,
    raw: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(raw, 10)
    except ValueError:
        raise InvalidSettingError(key, "must be an integer") from None
    if not minimum <= value <= maximum:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}")
    return value


def _validate_local_host(raw: str) -> str:
    host = raw.strip()
    normalized = host.casefold()
    if normalized in {"localhost", ".", "(local)"}:
        return normalized
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise InvalidSettingError(MSSQL_HOST_KEY, "must be an explicit loopback endpoint") from None
    if not address.is_loopback:
        raise InvalidSettingError(MSSQL_HOST_KEY, "must be an explicit loopback endpoint")
    return address.compressed


def load_dotnet_database_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> DotNetDatabaseSettings:
    """Load the explicit DotNet provider without attempting a database connection."""

    values = _resolved_values(env_file, environ, process_environ)
    provider = normalize_choice(
        DB_PROVIDER_KEY,
        _required(values, DB_PROVIDER_KEY),
        {"dotnet"},
    )
    environment = normalize_choice(
        ENVIRONMENT_KEY,
        _required(values, ENVIRONMENT_KEY),
        {"development", "paper", "test"},
    )
    host = _validate_local_host(_required(values, MSSQL_HOST_KEY))
    port = _parse_bounded_integer(
        MSSQL_PORT_KEY,
        _required(values, MSSQL_PORT_KEY),
        minimum=1,
        maximum=65535,
    )
    database = _required(values, MSSQL_DATABASE_KEY)
    if database != "auto_trading_v2":
        raise InvalidSettingError(MSSQL_DATABASE_KEY, "must target database auto_trading_v2")
    timeout = _parse_bounded_integer(
        MSSQL_CONNECT_TIMEOUT_KEY,
        _required(values, MSSQL_CONNECT_TIMEOUT_KEY),
        minimum=1,
        maximum=60,
    )
    encrypt = parse_boolean(MSSQL_ENCRYPT_KEY, _required(values, MSSQL_ENCRYPT_KEY))
    trust_certificate = parse_boolean(
        MSSQL_TRUST_CERTIFICATE_KEY,
        _required(values, MSSQL_TRUST_CERTIFICATE_KEY),
    )
    return DotNetDatabaseSettings(
        provider=DatabaseProvider(provider),
        environment=environment,
        host=host,
        port=port,
        database=database,
        username=SecretValue(require_text(MSSQL_USERNAME_KEY, values.get(MSSQL_USERNAME_KEY))),
        password=SecretValue(require_text(MSSQL_PASSWORD_KEY, values.get(MSSQL_PASSWORD_KEY))),
        encrypt=encrypt,
        trust_server_certificate=trust_certificate,
        connect_timeout=timeout,
    )
