import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "src" / "auto_trading_v2"
DOMAIN = SOURCE / "domain" / "feature_outcomes"
SERVICE = SOURCE / "application" / "services" / "daily_feature_outcome_observation.py"


def _import_roots(paths: list[Path]) -> set[str]:
    roots: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_outcome_domain_has_no_infrastructure_or_network_dependency() -> None:
    paths = sorted(DOMAIN.glob("*.py"))
    imports = _import_roots(paths)

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


def test_service_reads_canonical_sources_and_has_no_execution_side_effects() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    for forbidden in (
        "market_data.",
        "requests",
        "httpx",
        "DailyMarketBarIngestion",
        "FeatureSnapshotCreationService",
        "DailyFeatureScoringService",
        "RecommendationCreationService",
        "TradeIntent",
        "PaperOrder",
        "PaperFill",
        "Telegram",
        "scheduler",
    ):
        assert forbidden not in text


def test_p4b1_surface_contains_no_prediction_label_or_actionable_fields() -> None:
    paths = [
        *sorted(DOMAIN.glob("*.py")),
        *sorted((SOURCE / "application" / "services").glob("daily_feature_outcome*.py")),
        SOURCE / "application" / "contracts" / "feature_outcomes.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

    for forbidden in (
        "calibrated_probability",
        "expected_value",
        "expected_return_prediction",
        "entry_price",
        "target_price",
        "stop_price",
        "barrier_label",
        "win_loss_label",
    ):
        assert forbidden not in text


def test_p4b1_python_modules_are_utf8_without_bom_and_at_most_300_lines() -> None:
    paths = [
        *sorted(DOMAIN.glob("*.py")),
        *sorted((SOURCE / "application" / "services").glob("daily_feature_outcome*.py")),
        *sorted((SOURCE / "adapters" / "persistence").glob("*feature_outcome*.py")),
        *sorted((SOURCE / "adapters" / "persistence" / "tables").glob("feature_outcome*.py")),
        *sorted((ROOT / "migrations" / "ddl").glob("feature_outcome*.py")),
    ]

    for path in paths:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        assert len(text.splitlines()) <= 300, path
        assert chr(0xFFFD) not in text, path
