"""Safely create and inspect the dedicated V2 development database."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.database import (
    ADMIN_URL_ENV,
    DatabaseConfigurationError,
    DatabaseUrl,
    create_database_engine,
)
from auto_trading_v2.adapters.persistence.database_admin import (
    DEVELOPMENT_DATABASE_NAME,
    DatabaseSafetyError,
    create_development_database,
    database_exists,
    inspect_server_info,
    validate_server_info,
    verify_target_connection,
)


def main() -> int:
    """Create only auto_trading_v2 and print a sanitized capability summary."""

    admin_engine = None
    target_engine = None
    try:
        admin_settings = DatabaseUrl.from_environment(ADMIN_URL_ENV).require_database("master")
        admin_engine = create_database_engine(admin_settings, autocommit=True)
        with admin_engine.connect() as connection:
            already_exists = database_exists(connection, DEVELOPMENT_DATABASE_NAME)
            server_info = inspect_server_info(connection, DEVELOPMENT_DATABASE_NAME)
            validate_server_info(server_info, require_create_permission=not already_exists)

        result = create_development_database(admin_engine)
        target_settings = admin_settings.for_database(DEVELOPMENT_DATABASE_NAME)
        target_engine = create_database_engine(target_settings)
        with target_engine.connect() as connection:
            verify_target_connection(connection, DEVELOPMENT_DATABASE_NAME)
            target_info = inspect_server_info(connection, DEVELOPMENT_DATABASE_NAME)
            validate_server_info(target_info, require_create_permission=False)

        print(f"database={result.database_name}")
        print(f"created={result.created}")
        print(f"product_version={target_info.product_version}")
        print(f"product_major_version={target_info.product_major_version}")
        print(f"edition={target_info.edition}")
        print(f"compatibility_level={target_info.compatibility_level}")
        print(f"can_create_database={target_info.can_create_database}")
        return 0
    except (DatabaseConfigurationError, DatabaseSafetyError) as exc:
        print(f"database setup blocked: {exc}")
        return 2
    except SQLAlchemyError as exc:
        print(f"database setup failed: {type(exc).__name__}")
        return 3
    finally:
        if target_engine is not None:
            target_engine.dispose()
        if admin_engine is not None:
            admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
