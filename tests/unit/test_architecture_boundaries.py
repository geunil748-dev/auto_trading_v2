import ast
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "auto_trading_v2"


def _python_files() -> list[Path]:
    return sorted(SOURCE_ROOT.rglob("*.py"))


def test_source_has_no_v1_or_unapproved_database_and_http_imports() -> None:
    forbidden_roots = {
        "auto_trading",
        "httpx",
        "psycopg",
        "requests",
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


def test_python_dotenv_is_confined_to_explicit_config_loader() -> None:
    dotenv_imports: set[str] = set()

    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] == "dotenv" for alias in node.names):
                    dotenv_imports.add(path.relative_to(SOURCE_ROOT).as_posix())
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] == "dotenv"
            ):
                dotenv_imports.add(path.relative_to(SOURCE_ROOT).as_posix())

    assert dotenv_imports == {"config/loader.py"}
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files())
    assert "load_dotenv(" not in source_text


def test_source_has_no_forbidden_runtime_packages() -> None:
    relative_paths = {path.relative_to(SOURCE_ROOT).as_posix() for path in _python_files()}
    forbidden_parts = {"broker", "database", "orders", "fills", "positions"}

    assert all(not forbidden_parts.intersection(path.split("/")) for path in relative_paths)


def test_application_and_domain_do_not_import_persistence_libraries() -> None:
    forbidden = {"sqlalchemy", "alembic", "pyodbc", "pythonnet", "clr", "System"}
    discovered: set[str] = set()

    for layer in ("application", "domain"):
        for path in sorted((SOURCE_ROOT / layer).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    discovered.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    discovered.add(node.module.split(".")[0])

    assert discovered.isdisjoint(forbidden)


def test_pythonnet_and_system_data_imports_are_confined_to_dotnet_adapter() -> None:
    import_paths: set[str] = set()
    reference_paths: set[str] = set()

    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        if any(name in source for name in ("pythonnet", '"clr"', '"System.Data')):
            reference_paths.add(path.relative_to(SOURCE_ROOT).as_posix())
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            roots: set[str] = set()
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
            if roots.intersection({"pythonnet", "clr", "System"}):
                import_paths.add(path.relative_to(SOURCE_ROOT).as_posix())

    assert reference_paths
    assert all(path.startswith("adapters/persistence/dotnet/") for path in import_paths)
    assert all(path.startswith("adapters/persistence/dotnet/") for path in reference_paths)


def test_source_has_no_environment_access_or_domain_wall_clock() -> None:
    domain_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((SOURCE_ROOT / "domain").rglob("*.py"))
    )

    assert "os.getenv" not in domain_text
    assert "os.environ" not in domain_text
    assert "load_dotenv" not in domain_text
    assert "auto_trading_v2.config" not in domain_text
    assert "datetime.now(" not in domain_text
    assert "date.today(" not in domain_text
    assert "time.time(" not in domain_text


def test_project_declares_only_approved_runtime_dependencies() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file:
        pyproject = tomllib.load(file)

    assert set(pyproject["project"]["dependencies"]) == {
        "alembic==1.18.5",
        "pyodbc==5.3.0",
        "python-dotenv==1.2.2",
        "pythonnet==3.1.0",
        "SQLAlchemy==2.0.51",
    }


def test_project_text_is_utf8_without_bom_or_replacement_characters() -> None:
    paths = [
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / ".gitignore",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "alembic.ini",
    ]
    paths += sorted((PROJECT_ROOT / "docs").rglob("*.md"))
    paths += _python_files()
    paths += sorted((PROJECT_ROOT / "migrations").rglob("*.py"))
    paths += sorted((PROJECT_ROOT / "scripts").rglob("*.py"))
    paths += sorted((PROJECT_ROOT / "tests").rglob("*.py"))
    replacement_character = chr(0xFFFD)
    mojibake_fragments = (
        replacement_character * 3,
        chr(0xEC),
        chr(0xEA),
        chr(0xED),
    )

    for path in paths:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        text = raw.decode("utf-8")
        assert replacement_character not in text, path
        assert all(fragment not in text for fragment in mojibake_fragments), path


def test_package_import_smoke() -> None:
    import auto_trading_v2
    from auto_trading_v2.domain import primitives

    assert auto_trading_v2.__version__ == "0.1.0"
    assert primitives.Symbol("AAPL").serialize() == "AAPL"
