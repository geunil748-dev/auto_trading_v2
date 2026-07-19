from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict

import pytest

from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings
from auto_trading_v2.config.models import (
    AppSettings,
    DatabaseProvider,
    KisSettings,
    SecretValue,
    TelegramSettings,
)


def _settings(secret: str) -> AppSettings:
    return AppSettings(
        environment="development",
        log_level="INFO",
        database=DotNetDatabaseSettings(
            provider=DatabaseProvider.DOTNET,
            environment="development",
            host="localhost",
            port=1433,
            database="auto_trading_v2",
            username=SecretValue("v2-test-user"),
            password=SecretValue(secret),
            encrypt=False,
            trust_server_certificate=True,
            connect_timeout=5,
        ),
        kis=KisSettings(False, "paper", None, None, None, None, None),
        telegram=TelegramSettings(False, None, None),
    )


def test_secret_value_requires_explicit_reveal_and_has_safe_representations() -> None:
    secret = "SHOULD_NEVER_APPEAR_7f82d9"
    value = SecretValue(secret)

    assert value.reveal() == secret
    assert secret not in repr(value)
    assert secret not in str(value)
    assert repr(value) == "SecretValue(<redacted>)"


@pytest.mark.parametrize("value", ["", "  "])
def test_secret_value_rejects_blank_values(value: str) -> None:
    with pytest.raises(ValueError) as caught:
        SecretValue(value)
    assert str(caught.value) == "SecretValue requires a non-empty value"


def test_secret_value_and_nested_settings_are_immutable() -> None:
    secret = SecretValue("protected")
    settings = _settings("protected")

    with pytest.raises(AttributeError):
        secret.changed = "no"  # type: ignore[attr-defined]
    with pytest.raises(FrozenInstanceError):
        settings.environment = "test"  # type: ignore[misc]


def test_dataclass_serialization_keeps_secret_wrapper_redacted() -> None:
    secret = "SHOULD_NEVER_APPEAR_7f82d9"
    serialized = asdict(_settings(secret))

    assert secret not in repr(serialized)
    assert isinstance(serialized["database"]["password"], SecretValue)
