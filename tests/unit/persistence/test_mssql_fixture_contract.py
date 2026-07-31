from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine

from auto_trading_v2.adapters.persistence.administration import (
    LocalSharedMemoryConnectionInfo,
)
from auto_trading_v2.adapters.persistence.database_admin import ServerInfo
from auto_trading_v2.adapters.persistence.dotnet import DotNetConnectionFactory
from auto_trading_v2.config import (
    DatabaseProvider,
    MssqlAdministrationSettings,
    MssqlAdministrationTransport,
    SecretValue,
)
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings
from tests.integration.persistence import conftest as fixture_module

LOCAL_INTEGRATED_URL = (
    "mssql+pyodbc://@localhost/master?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes"
)


def _administration_settings() -> MssqlAdministrationSettings:
    return MssqlAdministrationSettings(
        admin_url=SecretValue(LOCAL_INTEGRATED_URL),
        test_admin_url=None,
        admin_transport=MssqlAdministrationTransport.LOCAL_SHARED_MEMORY,
    )


def _server_info() -> ServerInfo:
    return ServerInfo(
        product_version="16.0",
        product_major_version=16,
        edition="Developer Edition",
        database_name="auto_trading_v2_test_fixture",
        compatibility_level=160,
        can_create_database=True,
        binary_collation_available=True,
    )


def _lpc_info() -> LocalSharedMemoryConnectionInfo:
    return LocalSharedMemoryConnectionInfo(
        database_matches=True,
        shared_memory=True,
        integrated_auth=True,
        auth_scheme="NTLM",
        can_create_database=True,
        can_alter_database=True,
    )


def _wire_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    admin_engine = MagicMock(spec=Engine)
    target_engine = MagicMock(spec=Engine)
    factory = MagicMock()
    factory.create_master_engine.return_value = admin_engine
    factory.create_target_engine.return_value = target_engine
    factory_type = MagicMock(return_value=factory)

    monkeypatch.setattr(
        fixture_module,
        "load_mssql_administration_settings",
        lambda: _administration_settings(),
    )
    monkeypatch.setattr(fixture_module, "MssqlAdministrationEngineFactory", factory_type)
    monkeypatch.setattr(
        fixture_module,
        "generate_test_database_name",
        lambda: "auto_trading_v2_test_fixture",
    )
    monkeypatch.setattr(
        fixture_module,
        "verify_local_shared_memory_connection",
        lambda *_a, **_k: _lpc_info(),
    )
    monkeypatch.setattr(fixture_module, "inspect_server_info", lambda *_a, **_k: _server_info())
    monkeypatch.setattr(fixture_module, "validate_server_info", lambda *_a, **_k: None)
    monkeypatch.setattr(fixture_module, "verify_target_connection", lambda *_a, **_k: None)
    monkeypatch.setattr(fixture_module, "create_test_database", MagicMock())
    monkeypatch.setattr(fixture_module, "drop_test_database", MagicMock(return_value=True))
    monkeypatch.setattr(fixture_module, "database_exists", MagicMock(return_value=False))
    return factory_type, factory, admin_engine, target_engine


def test_fixture_routes_admin_and_target_through_explicit_lpc_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory_type, factory, admin_engine, target_engine = _wire_fixture(monkeypatch)
    monkeypatch.setattr(
        fixture_module.TemporaryMssqlDatabase,
        "run_upgrade",
        lambda _self, _revision="head": None,
    )

    with fixture_module.temporary_mssql_database() as database:
        assert database.administration_transport is MssqlAdministrationTransport.LOCAL_SHARED_MEMORY
        assert database.engine is target_engine

    factory_type.assert_called_once()
    factory.create_master_engine.assert_called_once_with()
    factory.create_target_engine.assert_called_once_with("auto_trading_v2_test_fixture")
    fixture_module.drop_test_database.assert_called_once_with(
        admin_engine,
        "auto_trading_v2_test_fixture",
    )
    target_engine.dispose.assert_called_once_with()
    admin_engine.dispose.assert_called_once_with()


def test_fixture_cleans_up_when_migration_upgrade_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, admin_engine, target_engine = _wire_fixture(monkeypatch)

    def fail_upgrade(_self: object, _revision: str = "head") -> None:
        raise RuntimeError("safe scripted migration failure")

    monkeypatch.setattr(
        fixture_module.TemporaryMssqlDatabase,
        "run_upgrade",
        fail_upgrade,
    )

    with (
        pytest.raises(RuntimeError, match="safe scripted migration failure"),
        fixture_module.temporary_mssql_database(),
    ):
        pytest.fail("fixture must fail before yield")

    fixture_module.drop_test_database.assert_called_once_with(
        admin_engine,
        "auto_trading_v2_test_fixture",
    )
    target_engine.dispose.assert_called_once_with()
    admin_engine.dispose.assert_called_once_with()


def test_dotnet_target_uses_official_sql_auth_settings_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = DotNetDatabaseSettings(
        provider=DatabaseProvider.DOTNET,
        environment="development",
        host="localhost",
        port=1433,
        database="auto_trading_v2",
        username=SecretValue("user-sentinel"),
        password=SecretValue("password-sentinel"),
        encrypt=False,
        trust_server_certificate=True,
        connect_timeout=5,
    )
    monkeypatch.setattr(
        fixture_module,
        "load_dotnet_database_settings",
        lambda: runtime,
    )

    factory = fixture_module.dotnet_sql_auth_connection_factory(
        SimpleNamespace(name="auto_trading_v2_test_dotnet")  # type: ignore[arg-type]
    )

    assert type(factory) is DotNetConnectionFactory
    assert factory.settings.environment == "test"
    assert factory.settings.database == "auto_trading_v2_test_dotnet"
    assert factory.settings.host == runtime.host
    assert factory.settings.port == runtime.port
    assert factory.settings.username is runtime.username
    assert factory.settings.password is runtime.password
    assert "user-sentinel" not in repr(factory)
    assert "password-sentinel" not in repr(factory)
