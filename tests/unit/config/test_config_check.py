from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from auto_trading_v2.config.loader import (
    KIS_APP_SECRET_KEY,
    KIS_ENABLED_KEY,
)
from scripts.check_config import run_check

from .helpers import DOTNET_DATABASE_ENVIRONMENT, valid_process_environment, write_env


def test_valid_diagnostic_prints_only_status_sources_and_counts(tmp_path: Path) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        {
            **DOTNET_DATABASE_ENVIRONMENT,
            "UNKNOWN_CREDENTIAL_NAME": sentinel,
        },
    )
    output = StringIO()

    exit_code = run_check(env_file=env_file, process_environ={}, output=output)

    rendered = output.getvalue()
    assert exit_code == 0
    assert "Configuration: VALID" in rendered
    assert "provider: dotnet (source=dotenv)" in rendered
    assert "Unknown keys: 1" in rendered
    assert "UNKNOWN_CREDENTIAL_NAME" not in rendered
    assert sentinel not in rendered
    assert "localhost" not in rendered


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
        environ=DOTNET_DATABASE_ENVIRONMENT,
        process_environ={},
        output=output,
    )

    rendered = output.getvalue()
    assert exit_code == 0
    assert "source=explicit" in rendered
    assert "localhost" not in rendered


def test_diagnostic_never_writes_secrets_to_stdout_or_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    env_file = tmp_path / ".env"
    write_env(env_file, {**DOTNET_DATABASE_ENVIRONMENT, "UNKNOWN_SECRET": sentinel})

    exit_code = run_check(env_file=env_file, process_environ={})
    captured = capsys.readouterr()

    assert exit_code == 0
    assert sentinel not in captured.out
    assert sentinel not in captured.err
