from pathlib import Path

import pytest

from auto_trading_v2.config import InvalidSettingError, MissingSettingError
from auto_trading_v2.config.dotnet_database import (
    DB_PROVIDER_KEY,
    DOTNET_DATABASE_KEYS,
    ENVIRONMENT_KEY,
    MSSQL_CONNECT_TIMEOUT_KEY,
    MSSQL_DATABASE_KEY,
    MSSQL_ENCRYPT_KEY,
    MSSQL_HOST_KEY,
    MSSQL_PASSWORD_KEY,
    MSSQL_PORT_KEY,
    MSSQL_TRUST_CERTIFICATE_KEY,
    MSSQL_USERNAME_KEY,
    inspect_dotnet_database_settings,
    load_dotnet_database_settings,
)

SENTINEL = "DOTNET_SECRET_SENTINEL_291ce7"


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        DB_PROVIDER_KEY: "dotnet",
        MSSQL_HOST_KEY: "localhost",
        MSSQL_PORT_KEY: "1433",
        MSSQL_DATABASE_KEY: "auto_trading_v2",
        MSSQL_USERNAME_KEY: f"user_{SENTINEL}",
        MSSQL_PASSWORD_KEY: SENTINEL,
        MSSQL_ENCRYPT_KEY: "false",
        MSSQL_TRUST_CERTIFICATE_KEY: "true",
        MSSQL_CONNECT_TIMEOUT_KEY: "5",
        ENVIRONMENT_KEY: "development",
    }
    values.update(overrides)
    return values


def _load(tmp_path: Path, values: dict[str, str]):
    return load_dotnet_database_settings(
        tmp_path / "missing.env",
        process_environ=values,
    )


def test_valid_settings_are_local_and_secret_safe(tmp_path: Path) -> None:
    settings = _load(tmp_path, _environment())

    assert settings.provider == "dotnet"
    assert settings.database == "auto_trading_v2"
    assert settings.data_source == "tcp:localhost,1433"
    rendered = repr(settings)
    assert SENTINEL not in rendered
    assert "localhost" not in rendered
    assert settings.username.reveal().endswith(SENTINEL)
    assert settings.password.reveal() == SENTINEL


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", ".", "(local)"])
def test_explicit_loopback_hosts_are_allowed(tmp_path: Path, host: str) -> None:
    assert _load(tmp_path, _environment(**{MSSQL_HOST_KEY: host})).host


@pytest.mark.parametrize(
    "host",
    ["example.test", "192.168.1.10", "10.0.0.2", "computer-name", "localhost\\SQLEXPRESS"],
)
def test_non_loopback_or_ambiguous_hosts_are_rejected(tmp_path: Path, host: str) -> None:
    with pytest.raises(InvalidSettingError) as caught:
        _load(tmp_path, _environment(**{MSSQL_HOST_KEY: host}))
    assert host not in str(caught.value)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (DB_PROVIDER_KEY, "pyodbc"),
        (MSSQL_DATABASE_KEY, f"wrong_{SENTINEL}"),
        (MSSQL_PORT_KEY, "0"),
        (MSSQL_PORT_KEY, "65536"),
        (MSSQL_CONNECT_TIMEOUT_KEY, "0"),
        (ENVIRONMENT_KEY, "production"),
    ],
)
def test_unsafe_or_invalid_settings_are_rejected_without_values(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    with pytest.raises(InvalidSettingError) as caught:
        _load(tmp_path, _environment(**{key: value}))
    assert value not in str(caught.value) or value in {"0"}


def test_provider_is_required_and_inventory_contains_counts_only(tmp_path: Path) -> None:
    values = _environment()
    del values[DB_PROVIDER_KEY]

    inventory = inspect_dotnet_database_settings(
        tmp_path / "missing.env",
        process_environ=values,
    )

    assert inventory.configured_count == len(DOTNET_DATABASE_KEYS) - 1
    assert inventory.missing_count == 1
    with pytest.raises(MissingSettingError):
        _load(tmp_path, values)
