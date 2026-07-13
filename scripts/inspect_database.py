"""Inspect the configured V2 database without mutating server state."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.database import (
    DATABASE_URL_ENV,
    DatabaseConfigurationError,
    DatabaseUrl,
    create_database_engine,
)
from auto_trading_v2.adapters.persistence.database_admin import (
    DEVELOPMENT_DATABASE_NAME,
    DatabaseSafetyError,
    inspect_existing_database,
    inspect_server_info,
    validate_server_info,
    verify_target_connection,
)


def main() -> int:
    """Print a credential-free SQL Server and canonical schema summary."""

    engine = None
    try:
        settings = DatabaseUrl.from_environment(DATABASE_URL_ENV).require_database(
            DEVELOPMENT_DATABASE_NAME
        )
        engine = create_database_engine(settings)
        with engine.connect() as connection:
            verify_target_connection(connection, DEVELOPMENT_DATABASE_NAME)
            server_info = inspect_server_info(connection, DEVELOPMENT_DATABASE_NAME)
            validate_server_info(server_info, require_create_permission=False)
            state = inspect_existing_database(connection, DEVELOPMENT_DATABASE_NAME)

        print(f"database={state.database_name}")
        print(f"product_version={server_info.product_version}")
        print(f"product_major_version={server_info.product_major_version}")
        print(f"edition={server_info.edition}")
        print(f"compatibility_level={server_info.compatibility_level}")
        print(f"business_table_count={len(state.business_tables)}")
        print(f"alembic_revision={state.alembic_revision or 'none'}")
        return 0
    except (DatabaseConfigurationError, DatabaseSafetyError) as exc:
        print(f"database inspection blocked: {exc}")
        return 2
    except SQLAlchemyError as exc:
        print(f"database inspection failed: {type(exc).__name__}")
        return 3
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
