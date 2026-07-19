from __future__ import annotations

from pathlib import Path

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
)

RUNTIME_URL = (
    "mssql+pyodbc://localhost/auto_trading_v2?"
    "driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes"
)
ADMIN_URL = (
    "mssql+pyodbc://localhost/master?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes"
)

DOTNET_DATABASE_ENVIRONMENT = {
    DB_PROVIDER_KEY: "dotnet",
    MSSQL_HOST_KEY: "localhost",
    MSSQL_PORT_KEY: "1433",
    MSSQL_DATABASE_KEY: "auto_trading_v2",
    MSSQL_USERNAME_KEY: "v2-test-user",
    MSSQL_PASSWORD_KEY: "v2-test-password",
    MSSQL_ENCRYPT_KEY: "false",
    MSSQL_TRUST_CERTIFICATE_KEY: "true",
    MSSQL_CONNECT_TIMEOUT_KEY: "5",
    ENVIRONMENT_KEY: "development",
}


def valid_process_environment(**overrides: str) -> dict[str, str]:
    values = dict(DOTNET_DATABASE_ENVIRONMENT)
    values.update(overrides)
    return values


def write_env(path: Path, values: dict[str, str], *, encoding: str = "utf-8") -> None:
    rendered = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    path.write_text(rendered, encoding=encoding)
