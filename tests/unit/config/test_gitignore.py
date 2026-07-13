from __future__ import annotations

import subprocess
from pathlib import Path

from dotenv import dotenv_values

from auto_trading_v2.config.loader import CANONICAL_KEYS

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", path],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode == 0


def test_local_env_variants_are_ignored_but_example_is_trackable() -> None:
    assert _is_ignored(".env")
    assert _is_ignored(".env.local")
    assert _is_ignored(".env.test")
    assert not _is_ignored(".env.example")


def test_actual_env_is_not_staged() -> None:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", ".env"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.stdout.strip() == ""


def test_env_example_contains_only_canonical_keys_and_no_secret_values() -> None:
    values = dotenv_values(
        PROJECT_ROOT / ".env.example",
        encoding="utf-8",
        interpolate=False,
    )
    assert set(values) == CANONICAL_KEYS
    assert values["AUTO_TRADING_V2_MSSQL_ADMIN_URL"] == ""
    assert values["AUTO_TRADING_V2_DATABASE_URL"] == ""
    assert values["AUTO_TRADING_V2_TEST_ADMIN_URL"] == ""
    assert values["AUTO_TRADING_V2_KIS_APP_KEY"] == ""
    assert values["AUTO_TRADING_V2_KIS_APP_SECRET"] == ""
    assert values["AUTO_TRADING_V2_KIS_ACCOUNT_NUMBER"] == ""
    assert values["AUTO_TRADING_V2_TELEGRAM_BOT_TOKEN"] == ""
    assert values["AUTO_TRADING_V2_TELEGRAM_CHAT_ID"] == ""
