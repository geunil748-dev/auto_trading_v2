from dataclasses import asdict
from pathlib import Path

import pytest

from auto_trading_v2.config import (
    ALPACA_MARKET_DATA_KEYS,
    CANONICAL_KEYS,
    load_alpaca_market_data_settings,
)
from auto_trading_v2.config.alpaca_market_data_keys import (
    ALPACA_API_KEY_ID_KEY,
    ALPACA_API_SECRET_KEY,
    ALPACA_BASE_URL_KEY,
    ALPACA_CONNECT_TIMEOUT_KEY,
    ALPACA_ENABLED_KEY,
    ALPACA_FEED_KEY,
    ALPACA_MAXIMUM_PAGES_KEY,
    ALPACA_MAXIMUM_RETRY_ATTEMPTS_KEY,
    ALPACA_READ_TIMEOUT_KEY,
    ALPACA_REQUESTS_PER_MINUTE_KEY,
)
from auto_trading_v2.config.errors import InvalidSettingError, MissingSettingError

KEY_ID = "alpaca-key-id-sentinel"
SECRET = "alpaca-secret-sentinel"


def test_safe_defaults_are_disabled_and_exact() -> None:
    settings = load_alpaca_market_data_settings(
        Path("missing-alpaca.env"),
        {},
        process_environ={},
    )

    assert settings.enabled is False
    assert settings.base_url == "https://data.alpaca.markets"
    assert settings.feed == "iex"
    assert settings.api_key_id is None
    assert settings.api_secret_key is None
    assert settings.connect_timeout_seconds == 5
    assert settings.read_timeout_seconds == 15
    assert settings.requests_per_minute == 200
    assert settings.maximum_retry_attempts == 3
    assert settings.maximum_pages == 5


def test_enabled_requires_both_credentials_without_exposing_values() -> None:
    with pytest.raises(MissingSettingError) as raised:
        load_alpaca_market_data_settings(
            Path("missing-alpaca.env"),
            {ALPACA_ENABLED_KEY: "true", ALPACA_API_KEY_ID_KEY: KEY_ID},
            process_environ={},
        )

    assert SECRET not in str(raised.value)
    assert KEY_ID not in str(raised.value)


def test_explicit_values_override_dotenv_and_process(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"{ALPACA_ENABLED_KEY}=true\n"
        f"{ALPACA_API_KEY_ID_KEY}=dotenv-id\n"
        f"{ALPACA_API_SECRET_KEY}=dotenv-secret\n",
        encoding="utf-8",
    )
    settings = load_alpaca_market_data_settings(
        dotenv,
        {
            ALPACA_API_KEY_ID_KEY: KEY_ID,
            ALPACA_API_SECRET_KEY: SECRET,
        },
        process_environ={
            ALPACA_ENABLED_KEY: "false",
            ALPACA_API_KEY_ID_KEY: "process-id",
            ALPACA_API_SECRET_KEY: "process-secret",
        },
    )

    assert settings.enabled is True
    assert settings.api_key_id is not None
    assert settings.api_secret_key is not None
    assert settings.api_key_id.reveal() == KEY_ID
    assert settings.api_secret_key.reveal() == SECRET


@pytest.mark.parametrize(
    "url",
    (
        "http://data.alpaca.markets",
        "https://example.com",
        "https://data.alpaca.markets/path",
        "https://data.alpaca.markets:443",
        "https://user@data.alpaca.markets",
        "https://data.alpaca.markets?secret=x",
    ),
)
def test_only_exact_official_data_host_is_allowed(url: str) -> None:
    with pytest.raises(InvalidSettingError):
        load_alpaca_market_data_settings(
            Path("missing-alpaca.env"),
            {ALPACA_BASE_URL_KEY: url},
            process_environ={},
        )


def test_feed_is_exactly_iex_and_credentials_are_repr_safe() -> None:
    with pytest.raises(InvalidSettingError):
        load_alpaca_market_data_settings(
            Path("missing-alpaca.env"),
            {ALPACA_FEED_KEY: "sip"},
            process_environ={},
        )
    settings = load_alpaca_market_data_settings(
        Path("missing-alpaca.env"),
        {
            ALPACA_ENABLED_KEY: "true",
            ALPACA_API_KEY_ID_KEY: KEY_ID,
            ALPACA_API_SECRET_KEY: SECRET,
        },
        process_environ={},
    )

    rendered = f"{settings!r}|{settings!s}|{asdict(settings)!r}"
    assert KEY_ID not in rendered
    assert SECRET not in rendered
    assert ALPACA_MARKET_DATA_KEYS <= CANONICAL_KEYS


@pytest.mark.parametrize(
    ("key", "value"),
    (
        (ALPACA_CONNECT_TIMEOUT_KEY, "0"),
        (ALPACA_READ_TIMEOUT_KEY, "121"),
        (ALPACA_REQUESTS_PER_MINUTE_KEY, "0"),
        (ALPACA_MAXIMUM_RETRY_ATTEMPTS_KEY, "6"),
        (ALPACA_MAXIMUM_PAGES_KEY, "0"),
    ),
)
def test_numeric_settings_are_bounded(key: str, value: str) -> None:
    with pytest.raises(InvalidSettingError):
        load_alpaca_market_data_settings(
            Path("missing-alpaca.env"),
            {key: value},
            process_environ={},
        )
