import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src" / "auto_trading_v2"


def test_domain_has_no_persistence_imports() -> None:
    forbidden = {"sqlalchemy", "alembic", "pyodbc"}
    imported: set[str] = set()

    for path in (SOURCE_ROOT / "domain").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

    assert imported.isdisjoint(forbidden)


def test_runtime_has_no_create_all_orm_or_automatic_migration() -> None:
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(SOURCE_ROOT.rglob("*.py"))
    )

    assert "metadata.create_all" not in source_text
    assert "declarative_base" not in source_text
    assert "DeclarativeBase" not in source_text
    assert "command.upgrade" not in source_text


def test_repositories_do_not_control_transactions_or_configuration() -> None:
    repository_root = SOURCE_ROOT / "adapters" / "persistence" / "repositories"
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(repository_root.rglob("*.py"))
    )

    assert ".commit(" not in source_text
    assert ".rollback(" not in source_text
    assert ".begin(" not in source_text
    assert "create_engine" not in source_text
    assert "os.getenv" not in source_text
    assert "os.environ" not in source_text


def test_forbidden_dependencies_and_artifacts_are_absent() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    forbidden_dependencies = (
        "psycopg",
        "pymssql",
        "django",
        "flask-sqlalchemy",
        "pandas",
        "numpy",
        "testcontainers",
    )

    assert all(dependency not in pyproject for dependency in forbidden_dependencies)
    assert not list(PROJECT_ROOT.rglob("*.bak"))
    assert not list(PROJECT_ROOT.rglob("*.mdf"))
    assert not list(PROJECT_ROOT.rglob("*.ldf"))
