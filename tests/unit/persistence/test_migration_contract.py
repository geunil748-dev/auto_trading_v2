import ast
import re
from pathlib import Path

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES

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


def test_initial_revision_and_table_creation_set_are_stable() -> None:
    version = MIGRATIONS_ROOT / "versions" / "0001_create_mssql_canonical_schema.py"
    assert version.exists()
    assert 'revision: str = "0001_mssql_schema"' in version.read_text(encoding="utf-8")

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


def test_migration_table_columns_match_metadata_exactly() -> None:
    expected = {
        table.name: tuple(column.name for column in table.columns) for table in BUSINESS_TABLES
    }

    assert _migration_columns() == expected


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
