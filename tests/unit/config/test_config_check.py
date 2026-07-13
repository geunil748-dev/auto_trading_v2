from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from auto_trading_v2.config.loader import (
    DATABASE_URL_KEY,
    KIS_APP_SECRET_KEY,
    KIS_ENABLED_KEY,
)
from scripts.check_config import run_check

from .helpers import RUNTIME_URL, valid_process_environment, write_env


def test_valid_diagnostic_prints_only_status_sources_and_counts(tmp_path: Path) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        {
            DATABASE_URL_KEY: RUNTIME_URL,
            "UNKNOWN_CREDENTIAL_NAME": sentinel,
        },
    )
    output = StringIO()

    exit_code = run_check(env_file=env_file, process_environ={}, output=output)

    rendered = output.getvalue()
    assert exit_code == 0
    assert "Configuration: VALID" in rendered
    assert "runtime URL: configured (source=dotenv)" in rendered
    assert "Unknown keys: 1" in rendered
    assert "UNKNOWN_CREDENTIAL_NAME" not in rendered
    assert sentinel not in rendered
    assert RUNTIME_URL not in rendered


def test_invalid_diagnostic_identifies_missing_canonical_key_without_value(
    tmp_path: Path,
) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    env_file = tmp_path / ".env"
    write_env(env_file, {})
    process = valid_process_environment(**{KIS_ENABLED_KEY: "true"})
    process.update(
        {
            "AUTO_TRADING_V2_KIS_BASE_URL": "https://paper.example.test/api",
            "AUTO_TRADING_V2_KIS_APP_KEY": sentinel,
        }
    )
    output = StringIO()

    exit_code = run_check(env_file=env_file, process_environ=process, output=output)

    rendered = output.getvalue()
    assert exit_code == 2
    assert "Configuration: INVALID" in rendered
    assert KIS_APP_SECRET_KEY in rendered
    assert "is required" in rendered
    assert sentinel not in rendered


def test_explicit_mapping_is_reported_without_printing_its_value(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, {})
    output = StringIO()

    exit_code = run_check(
        env_file=env_file,
        environ={DATABASE_URL_KEY: RUNTIME_URL},
        process_environ={},
        output=output,
    )

    rendered = output.getvalue()
    assert exit_code == 0
    assert "source=explicit" in rendered
    assert RUNTIME_URL not in rendered


def test_diagnostic_never_writes_secrets_to_stdout_or_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    env_file = tmp_path / ".env"
    write_env(env_file, {DATABASE_URL_KEY: RUNTIME_URL, "UNKNOWN_SECRET": sentinel})

    exit_code = run_check(env_file=env_file, process_environ={})
    captured = capsys.readouterr()

    assert exit_code == 0
    assert sentinel not in captured.out
    assert sentinel not in captured.err
