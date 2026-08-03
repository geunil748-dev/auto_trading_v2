from dataclasses import FrozenInstanceError, asdict

import pytest

from auto_trading_v2.config import (
    CANONICAL_KEYS,
    ConfigurationError,
    InvalidSettingError,
    MissingSettingError,
    TwelveDataMarketDataSettings,
    load_twelve_data_market_data_settings,
)
from auto_trading_v2.config.twelve_data import (
    TWELVE_DATA_API_KEY,
    TWELVE_DATA_BASE_URL_KEY,
    TWELVE_DATA_CONNECT_TIMEOUT_KEY,
    TWELVE_DATA_DAILY_CREDIT_BUDGET_KEY,
    TWELVE_DATA_ENABLED_KEY,
)

SENTINEL = "twelve-data-setting-secret"


def test_disabled_settings_use_safe_defaults_without_api_key(tmp_path) -> None:
    settings = load_twelve_data_market_data_settings(
        tmp_path / "missing.env",
        process_environ={},
    )

    assert settings.enabled is False
    assert settings.base_url == "https://api.twelvedata.com"
    assert settings.api_key is None
    assert settings.credits_per_minute == 8
    assert settings.daily_credit_budget == 800


def test_enabled_settings_require_api_key(tmp_path) -> None:
    with pytest.raises(MissingSettingError) as raised:
        load_twelve_data_market_data_settings(
            tmp_path / "missing.env",
            {TWELVE_DATA_ENABLED_KEY: "true"},
            process_environ={},
        )

    assert TWELVE_DATA_API_KEY in str(raised.value)


def test_explicit_overrides_dotenv_and_process_without_network(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                f"{TWELVE_DATA_ENABLED_KEY}=true",
                f"{TWELVE_DATA_API_KEY}=dotenv-key",
            )
        ),
        encoding="utf-8",
    )

    settings = load_twelve_data_market_data_settings(
        env_file,
        {TWELVE_DATA_API_KEY: SENTINEL},
        process_environ={TWELVE_DATA_API_KEY: "process-key"},
    )

    assert settings.api_key is not None
    assert settings.api_key.reveal() == SENTINEL


def test_blank_dotenv_value_does_not_fall_through_to_process(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"{TWELVE_DATA_ENABLED_KEY}=true\n{TWELVE_DATA_API_KEY}=\n",
        encoding="utf-8",
    )

    with pytest.raises(MissingSettingError):
        load_twelve_data_market_data_settings(
            env_file,
            process_environ={TWELVE_DATA_API_KEY: SENTINEL},
        )


@pytest.mark.parametrize(
    "url",
    (
        "http://api.twelvedata.com",
        "https://user@example.test",
        "https://example.test?apikey=secret",
        "https://example.test/#fragment",
    ),
)
def test_base_url_requires_safe_https(tmp_path, url: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        load_twelve_data_market_data_settings(
            tmp_path / "missing.env",
            {TWELVE_DATA_BASE_URL_KEY: url},
            process_environ={},
        )

    assert url not in str(raised.value)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        (TWELVE_DATA_CONNECT_TIMEOUT_KEY, "0"),
        (TWELVE_DATA_CONNECT_TIMEOUT_KEY, "inf"),
        (TWELVE_DATA_DAILY_CREDIT_BUDGET_KEY, "0"),
    ),
)
def test_operational_bounds_are_enforced(tmp_path, key: str, value: str) -> None:
    with pytest.raises(InvalidSettingError):
        load_twelve_data_market_data_settings(
            tmp_path / "missing.env",
            {key: value},
            process_environ={},
        )


def test_repr_str_and_asdict_do_not_reveal_key(tmp_path) -> None:
    settings = load_twelve_data_market_data_settings(
        tmp_path / "missing.env",
        {TWELVE_DATA_ENABLED_KEY: "true", TWELVE_DATA_API_KEY: SENTINEL},
        process_environ={},
    )

    rendered = f"{settings!r}|{settings!s}|{asdict(settings)!r}"

    assert SENTINEL not in rendered
    assert "api_key_configured=True" in rendered


def test_settings_are_immutable_and_keys_are_canonical(tmp_path) -> None:
    settings = load_twelve_data_market_data_settings(
        tmp_path / "missing.env",
        process_environ={},
    )

    assert isinstance(settings, TwelveDataMarketDataSettings)
    assert TWELVE_DATA_API_KEY in CANONICAL_KEYS
    with pytest.raises(FrozenInstanceError):
        settings.enabled = True  # type: ignore[misc]
