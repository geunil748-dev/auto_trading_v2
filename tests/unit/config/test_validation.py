from __future__ import annotations

from pathlib import Path

import pytest

from auto_trading_v2.config import InvalidSettingError, MissingSettingError, load_settings
from auto_trading_v2.config.loader import (
    CANONICAL_KEYS,
    DATABASE_URL_KEY,
    ENVIRONMENT_KEY,
    KIS_ACCOUNT_NUMBER_KEY,
    KIS_ACCOUNT_PRODUCT_CODE_KEY,
    KIS_APP_KEY,
    KIS_APP_SECRET_KEY,
    KIS_BASE_URL_KEY,
    KIS_ENABLED_KEY,
    KIS_ENVIRONMENT_KEY,
    LOG_LEVEL_KEY,
    MSSQL_ADMIN_URL_KEY,
    MSSQL_TEST_ADMIN_URL_KEY,
    TELEGRAM_BOT_TOKEN_KEY,
    TELEGRAM_CHAT_ID_KEY,
    TELEGRAM_ENABLED_KEY,
)
from auto_trading_v2.config.validation import parse_boolean

from .helpers import ADMIN_URL, RUNTIME_URL, valid_process_environment


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", " TRUE ", "YeS"])
def test_documented_true_values_are_accepted(value: str) -> None:
    assert parse_boolean(KIS_ENABLED_KEY, value) is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off", " FALSE ", "OfF"])
def test_documented_false_values_are_accepted(value: str) -> None:
    assert parse_boolean(KIS_ENABLED_KEY, value) is False


def test_invalid_boolean_does_not_echo_the_value() -> None:
    value = "SHOULD_NEVER_APPEAR_7f82d9"
    with pytest.raises(InvalidSettingError) as caught:
        parse_boolean(KIS_ENABLED_KEY, value)
    assert value not in str(caught.value)


def test_application_defaults_and_normalization(tmp_path: Path) -> None:
    settings = load_settings(
        tmp_path / "missing.env",
        process_environ=valid_process_environment(**{LOG_LEVEL_KEY: " warning "}),
    )
    assert settings.environment == "development"
    assert settings.log_level == "WARNING"


@pytest.mark.parametrize(
    ("key", "value"),
    [(ENVIRONMENT_KEY, "production"), (LOG_LEVEL_KEY, "TRACE")],
)
def test_invalid_application_choices_are_rejected(tmp_path: Path, key: str, value: str) -> None:
    with pytest.raises(InvalidSettingError) as caught:
        load_settings(
            tmp_path / "missing.env",
            process_environ=valid_process_environment(**{key: value}),
        )
    assert caught.value.key == key
    assert value not in str(caught.value)


def test_database_urls_accept_only_canonical_dialect_and_database(tmp_path: Path) -> None:
    settings = load_settings(
        tmp_path / "missing.env",
        process_environ=valid_process_environment(),
    )
    assert settings.database.database_url.reveal() == RUNTIME_URL
    assert settings.database.admin_url is not None
    assert settings.database.test_admin_url is not None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (DATABASE_URL_KEY, "postgresql://localhost/auto_trading_v2"),
        (DATABASE_URL_KEY, "mssql+pyodbc://localhost/other"),
        (MSSQL_ADMIN_URL_KEY, RUNTIME_URL),
        (MSSQL_TEST_ADMIN_URL_KEY, RUNTIME_URL),
    ],
)
def test_invalid_database_urls_are_rejected_without_echo(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    process = valid_process_environment(**{key: f"{value}?password={sentinel}"})
    with pytest.raises(InvalidSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert caught.value.key == key
    assert sentinel not in str(caught.value)
    assert value not in str(caught.value)


def test_database_parse_error_never_echoes_raw_url(tmp_path: Path) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    raw = f"://{sentinel}"
    process = valid_process_environment(**{DATABASE_URL_KEY: raw})
    with pytest.raises(InvalidSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert raw not in str(caught.value)
    assert sentinel not in repr(caught.value)


def test_disabled_kis_ignores_and_discards_credentials(tmp_path: Path) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    process = valid_process_environment(
        **{
            KIS_ENABLED_KEY: "false",
            KIS_BASE_URL_KEY: f"http://user:{sentinel}@invalid/?query={sentinel}",
            KIS_APP_KEY: sentinel,
            KIS_APP_SECRET_KEY: sentinel,
            KIS_ACCOUNT_NUMBER_KEY: sentinel,
            KIS_ACCOUNT_PRODUCT_CODE_KEY: sentinel,
        }
    )
    settings = load_settings(tmp_path / "missing.env", process_environ=process)
    assert settings.kis.base_url is None
    assert settings.kis.app_key is None
    assert sentinel not in repr(settings)


def _enabled_kis_environment() -> dict[str, str]:
    return valid_process_environment(
        **{
            KIS_ENABLED_KEY: "true",
            KIS_ENVIRONMENT_KEY: "paper",
            KIS_BASE_URL_KEY: "https://paper.example.test/api",
            KIS_APP_KEY: "app-key",
            KIS_APP_SECRET_KEY: "app-secret",
            KIS_ACCOUNT_NUMBER_KEY: "account-number",
            KIS_ACCOUNT_PRODUCT_CODE_KEY: "product-code",
        }
    )


@pytest.mark.parametrize(
    "missing_key",
    [
        KIS_BASE_URL_KEY,
        KIS_APP_KEY,
        KIS_APP_SECRET_KEY,
        KIS_ACCOUNT_NUMBER_KEY,
        KIS_ACCOUNT_PRODUCT_CODE_KEY,
    ],
)
def test_enabled_kis_requires_every_setting(tmp_path: Path, missing_key: str) -> None:
    process = _enabled_kis_environment()
    process.pop(missing_key)
    with pytest.raises(MissingSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert caught.value.key == missing_key


@pytest.mark.parametrize("environment", ["live", "real"])
def test_kis_rejects_non_paper_environments(tmp_path: Path, environment: str) -> None:
    process = _enabled_kis_environment()
    process[KIS_ENVIRONMENT_KEY] = environment
    with pytest.raises(InvalidSettingError):
        load_settings(tmp_path / "missing.env", process_environ=process)


@pytest.mark.parametrize(
    "url",
    [
        "http://paper.example.test/api",
        "https://user@paper.example.test/api",
        "https://paper.example.test/api?query=value",
        "https://paper.example.test/api#fragment",
    ],
)
def test_kis_rejects_unsafe_base_urls(tmp_path: Path, url: str) -> None:
    process = _enabled_kis_environment()
    process[KIS_BASE_URL_KEY] = url
    with pytest.raises(InvalidSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert url not in str(caught.value)


def test_enabled_telegram_requires_token_and_chat_id(tmp_path: Path) -> None:
    process = valid_process_environment(**{TELEGRAM_ENABLED_KEY: "true"})
    with pytest.raises(MissingSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert caught.value.key == TELEGRAM_BOT_TOKEN_KEY

    process[TELEGRAM_BOT_TOKEN_KEY] = "bot-token"
    with pytest.raises(MissingSettingError) as caught:
        load_settings(tmp_path / "missing.env", process_environ=process)
    assert caught.value.key == TELEGRAM_CHAT_ID_KEY


def test_disabled_telegram_discards_supplied_values(tmp_path: Path) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_7f82d9"
    process = valid_process_environment(
        **{
            TELEGRAM_ENABLED_KEY: "false",
            TELEGRAM_BOT_TOKEN_KEY: sentinel,
            TELEGRAM_CHAT_ID_KEY: sentinel,
        }
    )
    settings = load_settings(tmp_path / "missing.env", process_environ=process)
    assert settings.telegram.bot_token is None
    assert settings.telegram.chat_id is None
    assert sentinel not in repr(settings)


def test_access_token_setting_is_not_part_of_the_boundary() -> None:
    assert "AUTO_TRADING_V2_KIS_ACCESS_TOKEN" not in CANONICAL_KEYS
    assert ADMIN_URL.startswith("mssql+pyodbc")
