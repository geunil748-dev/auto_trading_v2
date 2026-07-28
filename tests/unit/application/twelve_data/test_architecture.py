from pathlib import Path

from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_CAPABILITIES,
)

ROOT = Path("src/auto_trading_v2")


def test_domain_has_no_adapter_configuration_or_persistence_imports() -> None:
    domain = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "domain").rglob("*.py"))

    for forbidden in (
        "urllib",
        "auto_trading_v2.config",
        "sqlalchemy",
        "pythonnet",
        "TWELVE_DATA",
    ):
        assert forbidden not in domain


def test_twelve_data_adapter_has_no_execution_or_fallback_dependencies() -> None:
    adapter = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "adapters" / "market_data" / "twelve_data").rglob("*.py")
    )

    for forbidden in (
        "Recommendation",
        "TradeIntent",
        "PaperOrder",
        "broker",
        "YAHOO",
        "ALPACA",
        "AUTO_TRADING_V2_KIS",
        "requests",
        "httpx",
        "aiohttp",
    ):
        assert forbidden not in adapter


def test_provider_capability_forbids_implicit_adjusted_volume_claim() -> None:
    assert TWELVE_DATA_CAPABILITIES.supports_adjusted_volume is False
    assert TWELVE_DATA_CAPABILITIES.official is True
