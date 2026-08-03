from __future__ import annotations

import importlib
import logging
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import pyodbc
import pytest
import sqlalchemy

import auto_trading_v2.config as config_package
import auto_trading_v2.config.loader as loader_module
from auto_trading_v2.config import (
    InvalidSettingError,
    MssqlAdministrationSettings,
    MssqlAdministrationTransport,
    SecretValue,
    load_mssql_administration_settings,
    load_settings,
)
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings
from auto_trading_v2.config.mssql_administration_keys import (
    MSSQL_ADMIN_TRANSPORT_KEY,
    MSSQL_ADMIN_URL_KEY,
    MSSQL_TEST_ADMIN_TRANSPORT_KEY,
    MSSQL_TEST_ADMIN_URL_KEY,
)

from .helpers import valid_process_environment, write_env

SENTINEL = "ADMIN_SECRET_SENTINEL_83c6af"
ADMIN_URL = f"mssql+pyodbc://admin:{SENTINEL}@localhost/master?driver=ODBC+Driver+18+for+SQL+Server"
TEST_ADMIN_URL = (
    f"mssql+pyodbc://test:{SENTINEL}@127.0.0.1/master?driver=ODBC+Driver+18+for+SQL+Server"
)


def _load(
    tmp_path: Path,
    *,
    environ: dict[str, str] | None = None,
    process: dict[str, str] | None = None,
) -> MssqlAdministrationSettings:
    return load_mssql_administration_settings(
        tmp_path / "missing.env",
        environ,
        process_environ={} if process is None else process,
    )


def test_test_admin_only_is_selected(tmp_path: Path) -> None:
    settings = _load(tmp_path, environ={MSSQL_TEST_ADMIN_URL_KEY: TEST_ADMIN_URL})

    assert settings.admin_url is None
    assert settings.test_admin_url is settings.selected_admin_url
    assert settings.selected_admin_url is not None
    assert settings.selected_admin_url.reveal() == TEST_ADMIN_URL


def test_admin_only_is_fallback(tmp_path: Path) -> None:
    settings = _load(tmp_path, environ={MSSQL_ADMIN_URL_KEY: ADMIN_URL})

    assert settings.test_admin_url is None
    assert settings.admin_url is settings.selected_admin_url


def test_test_admin_is_preferred_when_both_are_configured(tmp_path: Path) -> None:
    settings = _load(
        tmp_path,
        environ={
            MSSQL_ADMIN_URL_KEY: ADMIN_URL,
            MSSQL_TEST_ADMIN_URL_KEY: TEST_ADMIN_URL,
        },
    )

    assert settings.selected_admin_url is settings.test_admin_url


def test_missing_administration_urls_are_allowed(tmp_path: Path) -> None:
    settings = _load(tmp_path)

    assert settings.admin_url is None
    assert settings.test_admin_url is None
    assert settings.selected_admin_url is None
    assert settings.admin_transport is MssqlAdministrationTransport.TCP_URL
    assert settings.test_admin_transport is MssqlAdministrationTransport.TCP_URL
    assert settings.selected_admin_transport is MssqlAdministrationTransport.TCP_URL


def test_explicit_test_transport_is_selected_with_test_admin_url(tmp_path: Path) -> None:
    settings = _load(
        tmp_path,
        environ={
            MSSQL_ADMIN_URL_KEY: ADMIN_URL,
            MSSQL_ADMIN_TRANSPORT_KEY: "tcp_url",
            MSSQL_TEST_ADMIN_URL_KEY: TEST_ADMIN_URL,
            MSSQL_TEST_ADMIN_TRANSPORT_KEY: "LOCAL_SHARED_MEMORY",
        },
    )

    assert settings.selected_admin_url is settings.test_admin_url
    assert settings.selected_admin_transport is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY


def test_admin_transport_is_selected_when_test_admin_url_is_absent(tmp_path: Path) -> None:
    settings = _load(
        tmp_path,
        environ={
            MSSQL_ADMIN_URL_KEY: ADMIN_URL,
            MSSQL_ADMIN_TRANSPORT_KEY: "local_shared_memory",
            MSSQL_TEST_ADMIN_TRANSPORT_KEY: "tcp_url",
        },
    )

    assert settings.selected_admin_url is settings.admin_url
    assert settings.selected_admin_transport is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY


def test_invalid_transport_is_rejected_without_exposing_value(tmp_path: Path) -> None:
    unsafe_value = f"unknown-{SENTINEL}"

    with pytest.raises(InvalidSettingError) as caught:
        _load(
            tmp_path,
            environ={MSSQL_ADMIN_TRANSPORT_KEY: unsafe_value},
        )

    assert unsafe_value not in str(caught.value)
    assert SENTINEL not in repr(caught.value)


def test_blank_transport_masks_process_and_uses_safe_default(tmp_path: Path) -> None:
    settings = _load(
        tmp_path,
        environ={MSSQL_TEST_ADMIN_TRANSPORT_KEY: ""},
        process={MSSQL_TEST_ADMIN_TRANSPORT_KEY: "local_shared_memory"},
    )

    assert settings.test_admin_transport is MssqlAdministrationTransport.TCP_URL


def test_explicit_dotenv_process_precedence(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    dotenv_url = ADMIN_URL.replace("localhost", "127.0.0.1")
    process_url = ADMIN_URL.replace("localhost", "::1")
    write_env(env_file, {MSSQL_ADMIN_URL_KEY: dotenv_url})

    settings = load_mssql_administration_settings(
        env_file,
        {MSSQL_ADMIN_URL_KEY: ADMIN_URL},
        process_environ={MSSQL_ADMIN_URL_KEY: process_url},
    )

    assert settings.admin_url is not None
    assert settings.admin_url.reveal() == ADMIN_URL


def test_dotenv_blank_does_not_restore_process_value(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, {MSSQL_TEST_ADMIN_URL_KEY: ""})

    settings = load_mssql_administration_settings(
        env_file,
        process_environ={MSSQL_TEST_ADMIN_URL_KEY: TEST_ADMIN_URL},
    )

    assert settings.test_admin_url is None


@pytest.mark.parametrize(
    "url",
    [
        f"postgresql://admin:{SENTINEL}@localhost/master",
        (
            f"mssql+pyodbc://admin:{SENTINEL}@localhost/not_master?"
            "driver=ODBC+Driver+18+for+SQL+Server"
        ),
        (f"mssql+pyodbc://admin:{SENTINEL}@localhost/master?driver=FreeTDS"),
        (
            f"mssql+pyodbc://admin:{SENTINEL}@localhost/master?"
            "driver=ODBC+Driver+18+for+SQL+Server&driver=other"
        ),
        f"not-a-url-{SENTINEL}",
    ],
)
def test_invalid_admin_urls_are_rejected_without_exposing_values(
    tmp_path: Path,
    url: str,
) -> None:
    with pytest.raises(InvalidSettingError) as caught:
        _load(tmp_path, environ={MSSQL_ADMIN_URL_KEY: url})

    assert SENTINEL not in str(caught.value)
    assert SENTINEL not in repr(caught.value)


def test_loader_does_not_require_runtime_or_application_settings(tmp_path: Path) -> None:
    settings = _load(tmp_path, environ={MSSQL_ADMIN_URL_KEY: ADMIN_URL})

    assert settings.selected_admin_url is not None


def test_loader_does_not_open_connections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("configuration loading must not open connections")

    monkeypatch.setattr(pyodbc, "connect", fail)
    monkeypatch.setattr(sqlalchemy, "create_engine", fail)

    assert _load(tmp_path, environ={MSSQL_ADMIN_URL_KEY: ADMIN_URL})


def test_model_is_immutable_and_all_representations_are_redacted(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _load(
        tmp_path,
        environ={
            MSSQL_ADMIN_URL_KEY: ADMIN_URL,
            MSSQL_TEST_ADMIN_URL_KEY: TEST_ADMIN_URL,
        },
    )

    with pytest.raises(FrozenInstanceError):
        settings.admin_url = None  # type: ignore[misc]

    rendered = (repr(settings), str(settings), repr(asdict(settings)))
    assert all(SENTINEL not in item for item in rendered)
    assert "localhost" not in repr(settings)
    assert "admin_transport='tcp_url'" in repr(settings)
    assert "test_admin_transport='tcp_url'" in repr(settings)

    with caplog.at_level(logging.INFO):
        logging.getLogger("admin-config-test").info("settings=%r", settings)
    assert SENTINEL not in caplog.text

    with pytest.raises(AssertionError) as caught:
        assert settings == "different"
    assert SENTINEL not in str(caught.value)


def test_runtime_settings_remain_dotnet_and_isolated(tmp_path: Path) -> None:
    runtime = load_settings(
        tmp_path / "missing.env",
        process_environ=valid_process_environment(),
    )
    administration = _load(
        tmp_path,
        environ={MSSQL_TEST_ADMIN_URL_KEY: TEST_ADMIN_URL},
    )

    assert isinstance(runtime.database, DotNetDatabaseSettings)
    assert not hasattr(runtime.database, "admin_url")
    assert not hasattr(runtime.database, "test_admin_url")
    assert isinstance(administration, MssqlAdministrationSettings)
    assert administration.selected_admin_url is not None


def test_package_import_does_not_read_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("package import must not read dotenv")

    monkeypatch.setattr(loader_module, "_read_env_file", fail_if_called)
    importlib.reload(config_package)


def test_secret_wrapper_is_reused() -> None:
    settings = MssqlAdministrationSettings(
        admin_url=SecretValue(ADMIN_URL),
        test_admin_url=None,
    )

    assert isinstance(settings.admin_url, SecretValue)
    assert settings.admin_transport is MssqlAdministrationTransport.TCP_URL
