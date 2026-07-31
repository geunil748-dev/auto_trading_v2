from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from auto_trading_v2.adapters.persistence.administration import (
    LocalSharedMemoryConnectionInfo,
    MssqlAdministrationEngineFactory,
    verify_local_shared_memory_connection,
)
from auto_trading_v2.adapters.persistence.database_admin import (
    DatabaseSafetyError,
    ServerInfo,
    create_test_database,
    database_exists,
    drop_test_database,
    generate_test_database_name,
    inspect_server_info,
    validate_server_info,
    verify_target_connection,
)
from auto_trading_v2.adapters.persistence.dotnet import (
    DotNetConnectionFactory,
    DotNetUnitOfWorkFactory,
)
from auto_trading_v2.config import (
    MssqlAdministrationTransport,
    load_mssql_administration_settings,
)
from auto_trading_v2.config.dotnet_database import load_dotnet_database_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class TemporaryMssqlDatabase:
    name: str = field(repr=False)
    engine: Engine = field(repr=False)
    alembic_config: Config = field(repr=False)
    server_info: ServerInfo = field(repr=False)
    administration_transport: MssqlAdministrationTransport
    lpc_connection_info: LocalSharedMemoryConnectionInfo | None = field(repr=False)

    def run_upgrade(self, revision: str = "head") -> None:
        self._run_alembic(command.upgrade, revision)

    def run_downgrade(self, revision: str) -> None:
        self._run_alembic(command.downgrade, revision)

    def run_check(self) -> None:
        with self.engine.begin() as connection:
            self.alembic_config.attributes["connection"] = connection
            try:
                command.check(self.alembic_config)
            finally:
                self.alembic_config.attributes.pop("connection", None)

    def _run_alembic(self, operation: Callable[[Config, str], None], revision: str) -> None:
        with self.engine.begin() as connection:
            self.alembic_config.attributes["connection"] = connection
            try:
                operation(self.alembic_config, revision)
            finally:
                self.alembic_config.attributes.pop("connection", None)


@contextmanager
def temporary_mssql_database() -> Iterator[TemporaryMssqlDatabase]:
    """Create and always remove one guarded temporary MSSQL database."""

    administration = load_mssql_administration_settings()
    if administration.selected_admin_url is None:
        pytest.skip(
            "AUTO_TRADING_V2_TEST_ADMIN_URL 또는 명시적 ADMIN_URL이 없어 "
            "MSSQL 통합 테스트를 건너뜁니다."
        )

    engine_factory = MssqlAdministrationEngineFactory(administration)
    admin_engine = engine_factory.create_master_engine()
    database_name = generate_test_database_name()
    target_engine: Engine | None = None
    database_created = False
    primary_error: BaseException | None = None
    cleanup_errors: list[Exception] = []
    try:
        with admin_engine.connect() as connection:
            lpc_info = (
                verify_local_shared_memory_connection(
                    connection,
                    expected_database="master",
                    require_admin_permissions=True,
                )
                if administration.selected_admin_transport
                is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY
                else None
            )
            admin_info = inspect_server_info(connection, database_name)
            validate_server_info(admin_info, require_create_permission=True)
        create_test_database(admin_engine, database_name)
        database_created = True

        target_engine = engine_factory.create_target_engine(database_name)
        with target_engine.connect() as connection:
            verify_target_connection(connection, database_name)
            if (
                administration.selected_admin_transport
                is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY
            ):
                verify_local_shared_memory_connection(
                    connection,
                    expected_database=database_name,
                    require_admin_permissions=False,
                )
            server_info = inspect_server_info(connection, database_name)
            validate_server_info(server_info, require_create_permission=False)

        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        temporary = TemporaryMssqlDatabase(
            database_name,
            target_engine,
            config,
            server_info,
            administration.selected_admin_transport,
            lpc_info,
        )
        temporary.run_upgrade()
        yield temporary
    except BaseException as exc:
        primary_error = exc
    finally:
        if target_engine is not None:
            try:
                target_engine.dispose()
            except Exception:
                cleanup_errors.append(DatabaseSafetyError("MSSQL_TARGET_ENGINE_DISPOSE_FAILED"))
        if database_created:
            try:
                if not drop_test_database(admin_engine, database_name):
                    raise DatabaseSafetyError("MSSQL_TEMPORARY_DATABASE_DROP_MISSING")
                with admin_engine.connect() as connection:
                    if database_exists(connection, database_name):
                        raise DatabaseSafetyError("MSSQL_TEMPORARY_DATABASE_RESIDUE")
            except Exception:
                cleanup_errors.append(
                    DatabaseSafetyError("MSSQL_TEMPORARY_DATABASE_CLEANUP_FAILED")
                )
        try:
            admin_engine.dispose()
        except Exception:
            cleanup_errors.append(DatabaseSafetyError("MSSQL_ADMIN_ENGINE_DISPOSE_FAILED"))

    if primary_error is not None:
        if cleanup_errors:
            raise BaseExceptionGroup(
                "MSSQL_TEMPORARY_DATABASE_OPERATION_AND_CLEANUP_FAILED",
                [primary_error, *cleanup_errors],
            )
        raise primary_error
    if cleanup_errors:
        raise ExceptionGroup("MSSQL_TEMPORARY_DATABASE_CLEANUP_FAILED", cleanup_errors)


@pytest.fixture(scope="session")
def mssql_database() -> Iterator[TemporaryMssqlDatabase]:
    with temporary_mssql_database() as database:
        yield database


@contextmanager
def temporary_dotnet_uow_factory(
    database: TemporaryMssqlDatabase,
) -> Iterator[DotNetUnitOfWorkFactory]:
    """Create an official SQL-auth SqlClient boundary for one temporary database."""

    yield DotNetUnitOfWorkFactory(dotnet_sql_auth_connection_factory(database))


def dotnet_sql_auth_connection_factory(
    database: TemporaryMssqlDatabase,
) -> DotNetConnectionFactory:
    runtime = load_dotnet_database_settings()
    settings = replace(
        runtime,
        environment="test",
        database=database.name,
    )
    return DotNetConnectionFactory(settings)
