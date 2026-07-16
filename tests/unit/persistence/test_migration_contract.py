import ast
import re
from io import StringIO
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES, metadata
from migrations.ddl import (
    create_execution_tables,
    create_market_tables,
    create_portfolio_tables,
    create_strategy_tables,
    create_trading_events,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_ROOT = PROJECT_ROOT / "migrations"


def _migration_text() -> str:
    paths = sorted(MIGRATIONS_ROOT.rglob("*.py"))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _migration_columns() -> dict[str, tuple[str, ...]]:
    discovered: dict[str, tuple[str, ...]] = {}
    for path in sorted((MIGRATIONS_ROOT / "ddl").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_table"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                continue
            table_name = node.args[0].value
            columns = tuple(
                argument.args[0].value
                for argument in node.args[1:]
                if isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Attribute)
                and argument.func.attr == "Column"
                and argument.args
                and isinstance(argument.args[0], ast.Constant)
            )
            discovered[table_name] = columns
    return discovered


def test_revision_chain_and_initial_table_creation_set_are_stable() -> None:
    version = MIGRATIONS_ROOT / "versions" / "0001_create_mssql_canonical_schema.py"
    additive = MIGRATIONS_ROOT / "versions" / "0002_add_position_decision_market_snapshot.py"
    assert version.exists()
    assert additive.exists()
    assert 'revision: str = "0001_mssql_schema"' in version.read_text(encoding="utf-8")
    additive_text = additive.read_text(encoding="utf-8")
    assert 'revision: str = "0002_position_snapshot"' in additive_text
    assert 'down_revision: str | None = "0001_mssql_schema"' in additive_text

    text = _migration_text()
    created = set(re.findall(r'op\.create_table\(\s*"([a-z_]+)"', text))
    assert created == {table.name for table in BUSINESS_TABLES}


def test_migration_contains_every_metadata_constraint_and_index_name() -> None:
    text = _migration_text()
    expected_names = {
        name
        for table in BUSINESS_TABLES
        for name in [
            *(constraint.name for constraint in table.constraints),
            *(index.name for index in table.indexes),
        ]
        if name is not None
    }

    missing = {name for name in expected_names if f'"{name}"' not in text}
    assert missing == set()


def test_offline_migration_preserves_frozen_check_constraint_names() -> None:
    output = StringIO()
    context = MigrationContext.configure(
        dialect=mssql.dialect(),
        opts={"as_sql": True, "output_buffer": output, "target_metadata": metadata},
    )
    operations = Operations(context)

    create_market_tables(operations)
    create_portfolio_tables(operations, positions_only=True)
    create_strategy_tables(operations)
    create_execution_tables(operations)
    create_portfolio_tables(operations, positions_only=False)
    create_trading_events(operations)

    ddl = output.getvalue()
    expected_names = {
        constraint.name
        for table in BUSINESS_TABLES
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    additive_names = {
        "ck_strategy_decisions_candidate_without_snapshot",
        "ck_strategy_decisions_position_requires_snapshot",
    }
    expected_names -= additive_names
    assert all(name in ddl for name in expected_names)
    assert all(f"ck_{table.name}_ck_{table.name}_" not in ddl for table in BUSINESS_TABLES)
    additive_text = (
        MIGRATIONS_ROOT / "versions" / "0002_add_position_decision_market_snapshot.py"
    ).read_text(encoding="utf-8")
    assert all(name in additive_text for name in additive_names)


def test_initial_migration_columns_plus_additive_column_match_metadata() -> None:
    expected = {
        table.name: tuple(column.name for column in table.columns) for table in BUSINESS_TABLES
    }
    expected["strategy_decisions"] = tuple(
        name for name in expected["strategy_decisions"] if name != "market_snapshot_id"
    )

    assert _migration_columns() == expected
    additive = (
        MIGRATIONS_ROOT / "versions" / "0002_add_position_decision_market_snapshot.py"
    ).read_text(encoding="utf-8")
    assert 'sa.Column("market_snapshot_id", uuid_type(), nullable=True)' in additive


def test_migration_has_no_database_creation_batch_separator_or_seed_data() -> None:
    text = _migration_text()
    upper = text.upper()

    assert "CREATE DATABASE" not in upper
    assert "DROP DATABASE" not in upper
    assert re.search(r"(?m)^\s*GO\s*$", text, flags=re.IGNORECASE) is None
    assert re.search(r"(?m)^\s*USE\s+", text, flags=re.IGNORECASE) is None
    assert "INSERT INTO" not in upper
    assert "METADATA.CREATE_ALL" not in upper


def test_alembic_environment_has_no_hardcoded_connection_url() -> None:
    env_text = (MIGRATIONS_ROOT / "env.py").read_text(encoding="utf-8")
    ini_text = (PROJECT_ROOT / "alembic.ini").read_text(encoding="utf-8")

    assert "AUTO_TRADING_V2_DATABASE_URL" not in ini_text
    assert "sqlalchemy.url =\n" in ini_text
    assert "DATABASE_URL_ENV" in env_text
    assert "target_metadata=target_metadata" in env_text
