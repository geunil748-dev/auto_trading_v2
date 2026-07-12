import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "auto_trading_v2"


def _python_files() -> list[Path]:
    return sorted(SOURCE_ROOT.rglob("*.py"))


def test_source_has_no_v1_db_http_or_environment_imports() -> None:
    forbidden_roots = {
        "auto_trading",
        "dotenv",
        "httpx",
        "psycopg",
        "requests",
        "sqlalchemy",
        "sqlite3",
    }
    discovered: set[str] = set()

    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                discovered.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                discovered.add(node.module.split(".")[0])

    assert discovered.isdisjoint(forbidden_roots)


def test_source_has_no_forbidden_runtime_packages() -> None:
    relative_paths = {path.relative_to(SOURCE_ROOT).as_posix() for path in _python_files()}
    forbidden_parts = {"broker", "database", "orders", "fills", "positions", "repositories"}

    assert all(not forbidden_parts.intersection(path.split("/")) for path in relative_paths)


def test_source_has_no_environment_access_or_domain_wall_clock() -> None:
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files())
    domain_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((SOURCE_ROOT / "domain").rglob("*.py"))
    )

    assert "os.getenv" not in source_text
    assert "os.environ" not in source_text
    assert "load_dotenv" not in source_text
    assert "datetime.now(" not in domain_text
    assert "date.today(" not in domain_text
    assert "time.time(" not in domain_text


def test_project_declares_no_runtime_dependencies() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "dependencies = []" in pyproject
    assert "python-dotenv" not in pyproject


def test_project_text_is_utf8_without_bom_or_replacement_characters() -> None:
    paths = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "pyproject.toml"]
    paths += sorted((PROJECT_ROOT / "docs").rglob("*.md"))
    paths += _python_files()
    paths += sorted((PROJECT_ROOT / "tests").rglob("*.py"))

    for path in paths:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        text = raw.decode("utf-8")
        assert chr(0xFFFD) not in text, path


def test_package_import_smoke() -> None:
    import auto_trading_v2
    from auto_trading_v2.domain import primitives

    assert auto_trading_v2.__version__ == "0.1.0"
    assert primitives.Symbol("AAPL").serialize() == "AAPL"
