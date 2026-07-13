"""Validate local V2 configuration without opening DB or network connections."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_trading_v2.config import (  # noqa: E402
    ConfigurationError,
    ConfigurationInventory,
    SettingsLoadResult,
    inspect_environment_file,
    load_settings_with_diagnostics,
)
from auto_trading_v2.config.loader import (  # noqa: E402
    DATABASE_URL_KEY,
    MSSQL_ADMIN_URL_KEY,
    MSSQL_TEST_ADMIN_URL_KEY,
)


def _source_file_status(inventory: ConfigurationInventory) -> str:
    return "configured" if inventory.source_file_present else "missing"


def _setting_status(value: object | None) -> str:
    return "configured" if value is not None else "missing"


def _source(result: SettingsLoadResult, key: str) -> str:
    return result.diagnostics.source_for(key).value


def _write_inventory(inventory: ConfigurationInventory, output: TextIO) -> None:
    print(f"Source file: {_source_file_status(inventory)}", file=output)
    print(
        "Canonical keys: "
        f"configured={inventory.canonical_configured_count} "
        f"missing={inventory.canonical_missing_count}",
        file=output,
    )
    print(f"Unknown keys: {inventory.unknown_key_count}", file=output)
    print(f"Legacy-looking keys: {inventory.legacy_key_count}", file=output)


def _write_valid(result: SettingsLoadResult, output: TextIO) -> None:
    settings = result.settings
    print("Configuration: VALID", file=output)
    _write_inventory(result.diagnostics.inventory, output)
    print(f"Environment: {settings.environment}", file=output)
    print("", file=output)
    print("Database:", file=output)
    print(f"  runtime URL: configured (source={_source(result, DATABASE_URL_KEY)})", file=output)
    print(
        f"  admin URL: {_setting_status(settings.database.admin_url)} "
        f"(source={_source(result, MSSQL_ADMIN_URL_KEY)})",
        file=output,
    )
    print(
        f"  test admin URL: {_setting_status(settings.database.test_admin_url)} "
        f"(source={_source(result, MSSQL_TEST_ADMIN_URL_KEY)})",
        file=output,
    )
    print("", file=output)
    print("KIS:", file=output)
    print(f"  enabled: {str(settings.kis.enabled).lower()}", file=output)
    kis_credentials = (
        _setting_status(settings.kis.app_key) if settings.kis.enabled else "not-required"
    )
    print(f"  credentials: {kis_credentials}", file=output)
    print("", file=output)
    print("Telegram:", file=output)
    print(f"  enabled: {str(settings.telegram.enabled).lower()}", file=output)
    telegram_credentials = (
        _setting_status(settings.telegram.bot_token)
        if settings.telegram.enabled
        else "not-required"
    )
    print(f"  credentials: {telegram_credentials}", file=output)


def _section_for(key: str) -> str:
    if key.startswith("AUTO_TRADING_V2_MSSQL") or key == DATABASE_URL_KEY:
        return "Database"
    if key.startswith("AUTO_TRADING_V2_KIS"):
        return "KIS"
    if key.startswith("AUTO_TRADING_V2_TELEGRAM"):
        return "Telegram"
    return "Application"


def run_check(
    *,
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    process_environ: Mapping[str, str] | None = None,
    output: TextIO | None = None,
) -> int:
    """Run a value-free diagnostic with injectable sources for deterministic tests."""

    target = output or sys.stdout
    inventory: ConfigurationInventory | None = None
    try:
        inventory = inspect_environment_file(env_file)
        result = load_settings_with_diagnostics(
            env_file,
            environ,
            process_environ=process_environ,
        )
    except ConfigurationError as exc:
        print("Configuration: INVALID", file=target)
        if inventory is not None:
            _write_inventory(inventory, target)
        print(f"{_section_for(exc.key)}:", file=target)
        print(f"  {exc.key}: {exc.reason}", file=target)
        return 2
    _write_valid(result, target)
    return 0


def main() -> int:
    """Validate the repository-root dotenv plus process environment."""

    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())
