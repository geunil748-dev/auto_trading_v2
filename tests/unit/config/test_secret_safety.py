from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

import pytest

from auto_trading_v2.config import InvalidSettingError, load_settings
from auto_trading_v2.config.loader import (
    KIS_ACCOUNT_NUMBER_KEY,
    KIS_ACCOUNT_PRODUCT_CODE_KEY,
    KIS_APP_KEY,
    KIS_APP_SECRET_KEY,
    KIS_BASE_URL_KEY,
    KIS_ENABLED_KEY,
    MSSQL_PASSWORD_KEY,
    MSSQL_USERNAME_KEY,
    TELEGRAM_BOT_TOKEN_KEY,
    TELEGRAM_CHAT_ID_KEY,
    TELEGRAM_ENABLED_KEY,
)

from .helpers import valid_process_environment

SENTINEL = "SHOULD_NEVER_APPEAR_7f82d9"


def _secret_environment() -> dict[str, str]:
    return valid_process_environment(
        **{
            MSSQL_USERNAME_KEY: SENTINEL,
            MSSQL_PASSWORD_KEY: SENTINEL,
            KIS_ENABLED_KEY: "true",
            KIS_BASE_URL_KEY: "https://paper.example.test/api",
            KIS_APP_KEY: SENTINEL,
            KIS_APP_SECRET_KEY: SENTINEL,
            KIS_ACCOUNT_NUMBER_KEY: SENTINEL,
            KIS_ACCOUNT_PRODUCT_CODE_KEY: SENTINEL,
            TELEGRAM_ENABLED_KEY: "true",
            TELEGRAM_BOT_TOKEN_KEY: SENTINEL,
            TELEGRAM_CHAT_ID_KEY: SENTINEL,
        }
    )


def test_nested_repr_str_and_serialization_do_not_expose_secrets(tmp_path: Path) -> None:
    settings = load_settings(
        tmp_path / "missing.env",
        process_environ=_secret_environment(),
    )
    rendered = (repr(settings), str(settings), repr(asdict(settings)))
    assert all(SENTINEL not in item for item in rendered)


def test_validation_exception_never_contains_the_supplied_secret(tmp_path: Path) -> None:
    process = _secret_environment()
    process[KIS_BASE_URL_KEY] = f"http://user:{SENTINEL}@invalid.test/?token={SENTINEL}"
    with pytest.raises(InvalidSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert SENTINEL not in str(caught.value)
    assert SENTINEL not in repr(caught.value)


def test_logging_and_pytest_assertion_representation_are_redacted(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = load_settings(
        tmp_path / "missing.env",
        process_environ=_secret_environment(),
    )
    with caplog.at_level(logging.INFO):
        logging.getLogger("config-test").info("settings=%r", settings)
    assert SENTINEL not in caplog.text

    with pytest.raises(AssertionError) as caught:
        assert settings == "different"
    assert SENTINEL not in str(caught.value)
