import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = PROJECT_ROOT / "src" / "auto_trading_v2"
CALENDAR_DOMAIN = SOURCE_ROOT / "domain" / "market_calendar"
CALENDAR_APPLICATION = (
    SOURCE_ROOT / "application" / "services" / "completed_session.py",
    SOURCE_ROOT / "application" / "services" / "completed_daily_bars_request.py",
    SOURCE_ROOT / "application" / "services" / "daily_market_bar_calendar.py",
)
CALENDAR_ADAPTERS = tuple(sorted((SOURCE_ROOT / "adapters" / "market_calendar").rglob("*.py")))


def _import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_calendar_domain_has_no_infrastructure_dependencies() -> None:
    forbidden = {
        "sqlalchemy",
        "alembic",
        "pyodbc",
        "pythonnet",
        "clr",
        "System",
        "urllib",
        "http",
        "dotenv",
        "os",
    }

    for path in sorted(CALENDAR_DOMAIN.glob("*.py")):
        assert _import_roots(path).isdisjoint(forbidden), path
        source = path.read_text(encoding="utf-8")
        assert "auto_trading_v2.config" not in source
        assert "auto_trading_v2.adapters" not in source


def test_calendar_code_uses_injected_time_and_zoneinfo_not_fixed_offsets() -> None:
    paths = [*sorted(CALENDAR_DOMAIN.glob("*.py")), *CALENDAR_APPLICATION]
    paths.extend(CALENDAR_ADAPTERS)
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "datetime.now(" not in source
    assert "date.today(" not in source
    assert "timezone(timedelta" not in source
    assert 'ZoneInfo("America/New_York")' in source


def test_provider_adapters_do_not_duplicate_holiday_rules_or_fallback() -> None:
    provider_root = SOURCE_ROOT / "adapters" / "market_data"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(provider_root.rglob("*.py"))
    )

    assert "2026-07-03" not in source
    assert "INDEPENDENCE_DAY_OBSERVED" not in source
    assert "automatic fallback" not in source.lower()


def test_runtime_calendar_adapters_have_no_network_database_or_wall_clock_calls() -> None:
    forbidden_imports = {"requests", "urllib", "http", "socket", "sqlalchemy", "pyodbc"}
    for path in CALENDAR_ADAPTERS:
        assert _import_roots(path).isdisjoint(forbidden_imports), path
        source = path.read_text(encoding="utf-8")
        assert "datetime.now(" not in source
        assert "date.today(" not in source
        assert "time.tzset(" not in source
        assert ".commit(" not in source
        assert ".add(" not in source


def test_calendar_slice_has_no_recommendation_or_order_connections() -> None:
    paths = [*sorted(CALENDAR_DOMAIN.glob("*.py")), *CALENDAR_APPLICATION]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "FeatureSnapshot" not in source
    assert "Recommendation" not in source
    assert "TradeIntent" not in source
    assert "PaperOrder" not in source
    assert "auto_trading" not in source.replace("auto_trading_v2", "")


def test_changed_calendar_python_modules_are_below_300_lines() -> None:
    paths = [
        *sorted(CALENDAR_DOMAIN.glob("*.py")),
        *CALENDAR_APPLICATION,
        SOURCE_ROOT / "adapters" / "market_calendar" / "us_equity_2026.py",
        *CALENDAR_ADAPTERS,
        SOURCE_ROOT / "application" / "contracts" / "completed_daily_bars.py",
        SOURCE_ROOT / "application" / "ports" / "market_calendar.py",
        SOURCE_ROOT / "application" / "services" / "alpaca_ingestion.py",
        SOURCE_ROOT / "application" / "services" / "twelve_data_ingestion.py",
    ]

    for path in paths:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 300, path
