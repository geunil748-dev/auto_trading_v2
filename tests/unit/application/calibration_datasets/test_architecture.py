import ast
from pathlib import Path

from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
)
from auto_trading_v2.domain.outcome_labels import DailyFeatureOutcomeLabel

ROOT = Path(__file__).resolve().parents[4]
DOMAIN_ROOTS = (
    ROOT / "src" / "auto_trading_v2" / "domain" / "outcome_labels",
    ROOT / "src" / "auto_trading_v2" / "domain" / "calibration_datasets",
)
SERVICE_FILES = (
    ROOT
    / "src"
    / "auto_trading_v2"
    / "application"
    / "services"
    / "daily_feature_outcome_label.py",
    ROOT
    / "src"
    / "auto_trading_v2"
    / "application"
    / "services"
    / "probability_calibration_dataset.py",
)


def test_new_domains_have_no_network_persistence_runtime_or_config_imports() -> None:
    forbidden = ("sqlalchemy", "pythonnet", "requests", "httpx", "urllib", "config")
    imports = []
    for root in DOMAIN_ROOTS:
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports.extend(
                node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            )
            imports.extend(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )

    assert not [name for name in imports if any(token in name.lower() for token in forbidden)]


def test_services_have_no_provider_recommendation_trade_or_order_boundary() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in SERVICE_FILES)
    forbidden = (
        "provider_adapter",
        "DailyMarketBarRepository",
        "Recommendation",
        "StrategyDecision",
        "TradeIntent",
        "PaperOrder",
        "broker",
        "telegram",
    )

    assert not [token for token in forbidden if token in text]


def test_new_records_have_no_probability_model_confidence_or_target_stop_fields() -> None:
    fields = {
        *DailyFeatureOutcomeLabel.__dataclass_fields__,
        *ProbabilityCalibrationDataset.__dataclass_fields__,
        *ProbabilityCalibrationDatasetItem.__dataclass_fields__,
    }
    forbidden = {
        "probability",
        "calibrated_probability",
        "confidence",
        "expected_value",
        "expected_return_prediction",
        "model_coefficient",
        "entry_price",
        "target_price",
        "stop_price",
    }

    assert fields.isdisjoint(forbidden)
