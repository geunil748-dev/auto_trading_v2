"""Alembic environment using only the explicit V2 database URL."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.database import (
    DATABASE_URL_ENV,
    DatabaseUrl,
    create_database_engine,
)
from auto_trading_v2.adapters.persistence.tables import metadata
from migrations.autogenerate import (
    compare_mssql_server_default,
    include_schema_object,
)

config = context.config
target_metadata = metadata


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=compare_mssql_server_default,
        include_object=include_schema_object,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema="dbo",
    )


def run_migrations_offline() -> None:
    """Generate MSSQL migration SQL without opening a connection."""

    settings = DatabaseUrl.from_environment(DATABASE_URL_ENV)
    context.configure(
        url=settings.sqlalchemy_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=compare_mssql_server_default,
        include_object=include_schema_object,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema="dbo",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with an injected connection or a V2-only engine."""

    injected = config.attributes.get("connection")
    if isinstance(injected, Connection):
        _configure(injected)
        with context.begin_transaction():
            context.run_migrations()
        return

    settings = DatabaseUrl.from_environment(DATABASE_URL_ENV)
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            _configure(connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
