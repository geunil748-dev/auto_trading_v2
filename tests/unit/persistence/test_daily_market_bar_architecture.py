import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src" / "auto_trading_v2"
DOMAIN_ROOT = SOURCE_ROOT / "domain" / "daily_market_bars"
BUILDER = SOURCE_ROOT / "application" / "feature_building" / "daily_technical.py"
BUILD_SERVICE = SOURCE_ROOT / "application" / "services" / "daily_technical_feature_snapshot.py"


def _import_roots(paths: list[Path]) -> set[str]:
    imports: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    return imports


def test_daily_market_bar_domain_has_no_runtime_or_provider_dependency() -> None:
    paths = sorted(DOMAIN_ROOT.glob("*.py"))
    imports = _import_roots(paths)
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert imports.isdisjoint(
        {
            "sqlalchemy",
            "alembic",
            "pyodbc",
            "pythonnet",
            "clr",
            "config",
            "requests",
            "httpx",
            "aiohttp",
        }
    )
    for forbidden in ("KIS", "Yahoo", "Polygon", "Finnhub", "credential", "raw_payload"):
        assert forbidden not in text


def test_pure_builder_has_no_orchestration_execution_or_network_link() -> None:
    text = BUILDER.read_text(encoding="utf-8")

    for forbidden in (
        "Repository",
        "UnitOfWork",
        "Clock",
        "UUID",
        "config",
        "requests",
        "httpx",
        "Recommendation",
        "TradeIntent",
        "PaperOrder",
        "PaperFill",
    ):
        assert forbidden not in text


def test_build_service_stops_at_feature_snapshot_creation() -> None:
    text = BUILD_SERVICE.read_text(encoding="utf-8")

    for forbidden in (
        "Recommendation",
        "TradeIntent",
        "PaperOrder",
        "PaperFill",
        "Telegram",
        "ranking",
        "probability",
    ):
        assert forbidden not in text


def test_no_actual_daily_market_provider_adapter_or_http_dependency_exists() -> None:
    source_paths = sorted(SOURCE_ROOT.rglob("*.py"))
    imports = _import_roots(source_paths)
    paths = {path.relative_to(SOURCE_ROOT).as_posix() for path in source_paths}

    assert imports.isdisjoint({"requests", "httpx", "aiohttp", "yfinance"})
    assert all("daily_market" not in path or "/brokers/" not in path for path in paths)
