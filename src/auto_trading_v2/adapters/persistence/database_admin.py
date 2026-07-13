"""Safety-checked V2 database creation, inspection, and test cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import Connection, Engine, text

from auto_trading_v2.adapters.persistence.database import (
    quote_database_identifier,
    validate_database_identifier,
)
from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES
from auto_trading_v2.adapters.persistence.types import BINARY_COLLATION

DEVELOPMENT_DATABASE_NAME = "auto_trading_v2"
TEST_DATABASE_PREFIX = "auto_trading_v2_test_"
EXPECTED_BUSINESS_TABLES = frozenset(table.name for table in BUSINESS_TABLES)


class DatabaseSafetyError(RuntimeError):
    """Raised before any unsafe or incompatible database operation."""


@dataclass(frozen=True, slots=True)
class ExistingDatabaseState:
    """Sanitized existing database schema summary."""

    database_name: str
    business_tables: frozenset[str]
    unexpected_tables: frozenset[str]
    alembic_revision: str | None


@dataclass(frozen=True, slots=True)
class DatabaseCreationResult:
    """Report whether a safe database creation changed server state."""

    database_name: str
    created: bool
    existing_state: ExistingDatabaseState | None


@dataclass(frozen=True, slots=True)
class ServerInfo:
    """Non-secret SQL Server capability summary."""

    product_version: str
    product_major_version: int
    edition: str
    database_name: str
    compatibility_level: int | None
    can_create_database: bool
    binary_collation_available: bool


def validate_development_database_name(database_name: str) -> str:
    """Allow only the canonical V2 development database name."""

    validate_database_identifier(database_name)
    if database_name != DEVELOPMENT_DATABASE_NAME:
        raise DatabaseSafetyError("development database 이름은 auto_trading_v2만 허용합니다.")
    return database_name


def validate_test_database_name(database_name: str) -> str:
    """Allow destructive operations only for uniquely prefixed test databases."""

    validate_database_identifier(database_name)
    if not database_name.startswith(TEST_DATABASE_PREFIX) or len(database_name) <= len(
        TEST_DATABASE_PREFIX
    ):
        raise DatabaseSafetyError("test database prefix가 올바르지 않습니다.")
    return database_name


def generate_test_database_name() -> str:
    """Generate a test-only database name that passes the deletion guard."""

    return f"{TEST_DATABASE_PREFIX}{uuid4().hex}"


def database_exists(connection: Connection, database_name: str) -> bool:
    """Check existence through DB_ID while binding the database name as data."""

    validate_database_identifier(database_name)
    value = connection.execute(
        text("SELECT DB_ID(:database_name)"), {"database_name": database_name}
    ).scalar_one_or_none()
    return value is not None


def inspect_existing_database(connection: Connection, database_name: str) -> ExistingDatabaseState:
    """Inspect existing user tables and revision without changing the database."""

    quoted = quote_database_identifier(database_name)
    rows = connection.exec_driver_sql(
        "SELECT s.name AS schema_name, t.name AS table_name "
        f"FROM {quoted}.sys.tables AS t "
        f"JOIN {quoted}.sys.schemas AS s ON t.schema_id = s.schema_id"
    ).mappings()
    qualified = {(str(row["schema_name"]), str(row["table_name"])) for row in rows}
    business = frozenset(name for schema, name in qualified if schema == "trading")
    allowed = {("trading", name) for name in EXPECTED_BUSINESS_TABLES}
    allowed.add(("dbo", "alembic_version"))
    unexpected = frozenset(f"{schema}.{name}" for schema, name in qualified - allowed)

    revision: str | None = None
    if ("dbo", "alembic_version") in qualified:
        revision_value = connection.exec_driver_sql(
            f"SELECT version_num FROM {quoted}.dbo.alembic_version"
        ).scalar_one_or_none()
        revision = None if revision_value is None else str(revision_value)

    state = ExistingDatabaseState(database_name, business, unexpected, revision)
    _validate_existing_state(state)
    return state


def _validate_existing_state(state: ExistingDatabaseState) -> None:
    if state.unexpected_tables:
        raise DatabaseSafetyError("예상하지 않은 기존 table이 있어 작업을 중단합니다.")
    if state.business_tables and state.business_tables != EXPECTED_BUSINESS_TABLES:
        raise DatabaseSafetyError("불완전하거나 알 수 없는 trading schema가 있어 중단합니다.")
    if state.business_tables and state.alembic_revision is None:
        raise DatabaseSafetyError("canonical table은 있으나 Alembic revision이 없습니다.")
    if not state.business_tables and state.alembic_revision is not None:
        raise DatabaseSafetyError("Alembic revision과 business table 상태가 일치하지 않습니다.")


def _create_database(connection: Connection, database_name: str) -> None:
    quoted = quote_database_identifier(database_name)
    connection.exec_driver_sql(f"CREATE DATABASE {quoted}")
    if not database_exists(connection, database_name):
        raise DatabaseSafetyError("database 생성 확인에 실패했습니다.")


def create_development_database(engine: Engine) -> DatabaseCreationResult:
    """Create the V2 development database if absent, never dropping existing state."""

    database_name = validate_development_database_name(DEVELOPMENT_DATABASE_NAME)
    with engine.connect() as connection:
        if database_exists(connection, database_name):
            state = inspect_existing_database(connection, database_name)
            return DatabaseCreationResult(database_name, False, state)
        _create_database(connection, database_name)
    return DatabaseCreationResult(database_name, True, None)


def create_test_database(engine: Engine, database_name: str) -> DatabaseCreationResult:
    """Create a validated unique test database using an autocommit admin engine."""

    validated = validate_test_database_name(database_name)
    with engine.connect() as connection:
        if database_exists(connection, validated):
            raise DatabaseSafetyError("test database가 이미 존재합니다.")
        _create_database(connection, validated)
    return DatabaseCreationResult(validated, True, None)


def drop_test_database(engine: Engine, database_name: str) -> bool:
    """Drop only a revalidated test database after confirming its exact server name."""

    validated = validate_test_database_name(database_name)
    quoted = quote_database_identifier(validated)
    with engine.connect() as connection:
        actual_name = connection.execute(
            text("SELECT name FROM sys.databases WHERE name = :database_name"),
            {"database_name": validated},
        ).scalar_one_or_none()
        if actual_name is None:
            return False
        if actual_name != validated:
            raise DatabaseSafetyError("test database 이름 재확인에 실패했습니다.")
        connection.exec_driver_sql(
            f"ALTER DATABASE {quoted} SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
        )
        connection.exec_driver_sql(f"DROP DATABASE {quoted}")
    return True


def verify_target_connection(connection: Connection, expected_database_name: str) -> None:
    """Require the connected target database to match the expected safe name."""

    validate_database_identifier(expected_database_name)
    actual = connection.exec_driver_sql("SELECT DB_NAME()").scalar_one()
    if actual != expected_database_name:
        raise DatabaseSafetyError("연결된 target database 이름이 예상과 다릅니다.")


def inspect_server_info(connection: Connection, database_name: str) -> ServerInfo:
    """Read non-secret server capabilities and target compatibility."""

    validate_database_identifier(database_name)
    row = (
        connection.exec_driver_sql(
            "SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) AS product_version, "
            "CAST(SERVERPROPERTY('ProductMajorVersion') AS int) AS product_major_version, "
            "CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) AS edition, "
            "CAST(HAS_PERMS_BY_NAME(NULL, NULL, 'CREATE ANY DATABASE') AS int) "
            "AS can_create_database"
        )
        .mappings()
        .one()
    )
    compatibility = connection.execute(
        text("SELECT compatibility_level FROM sys.databases WHERE name = :database_name"),
        {"database_name": database_name},
    ).scalar_one_or_none()
    collation_count = connection.execute(
        text("SELECT COUNT(*) FROM sys.fn_helpcollations() WHERE name = :collation"),
        {"collation": BINARY_COLLATION},
    ).scalar_one()
    return ServerInfo(
        product_version=str(row["product_version"]),
        product_major_version=int(row["product_major_version"]),
        edition=str(row["edition"]),
        database_name=database_name,
        compatibility_level=None if compatibility is None else int(compatibility),
        can_create_database=bool(row["can_create_database"]),
        binary_collation_available=int(collation_count) > 0,
    )


def validate_server_info(info: ServerInfo, *, require_create_permission: bool) -> None:
    """Reject unsupported SQL Server variants without changing server settings."""

    edition = info.edition.casefold()
    if "synapse" in edition or "data warehouse" in edition:
        raise DatabaseSafetyError("Azure Synapse/Data Warehouse는 지원 대상으로 간주하지 않습니다.")
    if info.product_major_version < 13:
        raise DatabaseSafetyError("SQL Server 2016 이상이 필요합니다.")
    if info.compatibility_level is not None and info.compatibility_level < 130:
        raise DatabaseSafetyError("database compatibility level 130 이상이 필요합니다.")
    if not info.binary_collation_available:
        raise DatabaseSafetyError("필수 binary collation을 사용할 수 없습니다.")
    if require_create_permission and not info.can_create_database:
        raise DatabaseSafetyError("현재 login에 CREATE DATABASE 권한이 없습니다.")
