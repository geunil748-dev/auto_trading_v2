from __future__ import annotations

from pathlib import Path

from auto_trading_v2.config.loader import (
    DATABASE_URL_KEY,
    MSSQL_ADMIN_URL_KEY,
    MSSQL_TEST_ADMIN_URL_KEY,
)

RUNTIME_URL = (
    "mssql+pyodbc://localhost/auto_trading_v2?"
    "driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes"
)
ADMIN_URL = (
    "mssql+pyodbc://localhost/master?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes"
)


def valid_process_environment(**overrides: str) -> dict[str, str]:
    values = {
        DATABASE_URL_KEY: RUNTIME_URL,
        MSSQL_ADMIN_URL_KEY: ADMIN_URL,
        MSSQL_TEST_ADMIN_URL_KEY: ADMIN_URL,
    }
    values.update(overrides)
    return values


def write_env(path: Path, values: dict[str, str], *, encoding: str = "utf-8") -> None:
    rendered = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    path.write_text(rendered, encoding=encoding)
