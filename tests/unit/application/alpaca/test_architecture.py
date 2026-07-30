from pathlib import Path

from auto_trading_v2.adapters.market_data.alpaca import ALPACA_CAPABILITIES

ROOT = Path("src/auto_trading_v2")


def test_alpaca_adapter_has_no_trading_feature_or_fallback_dependencies() -> None:
    adapter = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "adapters" / "market_data" / "alpaca").rglob("*.py")
    )

    for forbidden in (
        "FeatureSnapshot",
        "Recommendation",
        "TradeIntent",
        "PaperOrder",
        "broker",
        "TWELVE_DATA",
        "YAHOO",
        "AUTO_TRADING_V2_KIS",
        "import requests",
        "httpx",
        "aiohttp",
    ):
        assert forbidden not in adapter


def test_comparison_service_is_read_only_and_has_no_selection_policy() -> None:
    source = (ROOT / "application" / "services" / "daily_bar_comparison.py").read_text(
        encoding="utf-8"
    )

    for forbidden in (
        ".add(",
        ".commit(",
        "FeatureSnapshot",
        "Recommendation",
        "TradeIntent",
        "PaperOrder",
        "fallback",
        "threshold",
    ):
        assert forbidden not in source


def test_alpaca_capabilities_are_explicitly_volume_and_pagination_aware() -> None:
    assert ALPACA_CAPABILITIES.supports_adjusted_volume is True
    assert ALPACA_CAPABILITIES.supports_pagination is True
    assert ALPACA_CAPABILITIES.maximum_rows_per_request == 10_000
