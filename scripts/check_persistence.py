"""Read-only validation of the configured V2 persistence target."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import Engine, inspect, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from auto_trading_v2.adapters.persistence.database_admin import (  # noqa: E402
    DEVELOPMENT_DATABASE_NAME,
    EXPECTED_BUSINESS_TABLES,
)
from auto_trading_v2.adapters.persistence.engine import create_mssql_engine  # noqa: E402
from auto_trading_v2.config import (  # noqa: E402
    ConfigurationError,
    SettingSource,
    load_settings_with_diagnostics,
)
from auto_trading_v2.config.loader import DATABASE_URL_KEY  # noqa: E402

EXPECTED_REVISION = "0001_mssql_schema"


class PersistenceDiagnosticError(RuntimeError):
    """A value-free diagnostic invariant failure."""


def run_check(*, output: TextIO | None = None) -> int:
    """Inspect configuration and canonical schema without changing database state."""

    target = output or sys.stdout
    engine: Engine | None = None
    stage = "configuration"
    try:
        result = load_settings_with_diagnostics()
        source = result.diagnostics.source_for(DATABASE_URL_KEY)
        if source is not SettingSource.DOTENV:
            raise PersistenceDiagnosticError

        stage = "engine"
        engine = create_mssql_engine(result.settings.database)
        stage = "connection"
        with engine.connect() as connection:
            database_name = connection.exec_driver_sql("SELECT DB_NAME()").scalar_one()
            if database_name != DEVELOPMENT_DATABASE_NAME:
                raise PersistenceDiagnosticError

            stage = "schema"
            inspector = inspect(connection)
            if "trading" not in inspector.get_schema_names():
                raise PersistenceDiagnosticError
            table_names = frozenset(inspector.get_table_names(schema="trading"))
            if table_names != EXPECTED_BUSINESS_TABLES:
                raise PersistenceDiagnosticError

            stage = "migration"
            revision = connection.execute(
                text("SELECT version_num FROM dbo.alembic_version")
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                raise PersistenceDiagnosticError
    except (ConfigurationError, PersistenceDiagnosticError, SQLAlchemyError):
        print("Persistence: NOT_READY", file=target)
        print(f"Stage: {stage}", file=target)
        return 2
    finally:
        if engine is not None:
            engine.dispose()

    print("Persistence: READY", file=target)
    print("Configuration source: dotenv", file=target)
    print("Connection: ok", file=target)
    print("Schema: trading", file=target)
    print(f"Canonical tables: {len(EXPECTED_BUSINESS_TABLES)}", file=target)
    print("Migration: head", file=target)
    return 0


def main() -> int:
    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())
