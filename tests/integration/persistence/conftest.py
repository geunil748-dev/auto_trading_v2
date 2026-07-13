from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from auto_trading_v2.adapters.persistence.database import (
    ADMIN_URL_ENV,
    TEST_ADMIN_URL_ENV,
    DatabaseUrl,
    create_database_engine,
)
from auto_trading_v2.adapters.persistence.database_admin import (
    ServerInfo,
    create_test_database,
    drop_test_database,
    generate_test_database_name,
    inspect_server_info,
    validate_server_info,
    verify_target_connection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class TemporaryMssqlDatabase:
    name: str = field(repr=False)
    engine: Engine = field(repr=False)
    alembic_config: Config = field(repr=False)
    server_info: ServerInfo = field(repr=False)

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


@pytest.fixture(scope="session")
def mssql_database() -> Iterator[TemporaryMssqlDatabase]:
    raw_admin_url = os.environ.get(TEST_ADMIN_URL_ENV) or os.environ.get(ADMIN_URL_ENV)
    if not raw_admin_url:
        pytest.skip(
            "AUTO_TRADING_V2_TEST_ADMIN_URL 또는 명시적 ADMIN_URL이 없어 "
            "MSSQL 통합 테스트를 건너뜁니다."
        )

    admin_settings = DatabaseUrl(raw_admin_url).require_database("master")
    admin_engine = create_database_engine(admin_settings, autocommit=True)
    database_name = generate_test_database_name()
    target_engine: Engine | None = None
    database_created = False
    try:
        with admin_engine.connect() as connection:
            admin_info = inspect_server_info(connection, database_name)
            validate_server_info(admin_info, require_create_permission=True)
        create_test_database(admin_engine, database_name)
        database_created = True

        target_settings = admin_settings.for_database(database_name)
        target_engine = create_database_engine(target_settings)
        with target_engine.connect() as connection:
            verify_target_connection(connection, database_name)
            server_info = inspect_server_info(connection, database_name)
            validate_server_info(server_info, require_create_permission=False)

        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        temporary = TemporaryMssqlDatabase(database_name, target_engine, config, server_info)
        temporary.run_upgrade()
        yield temporary
    finally:
        if target_engine is not None:
            target_engine.dispose()
        if database_created:
            drop_test_database(admin_engine, database_name)
        admin_engine.dispose()
