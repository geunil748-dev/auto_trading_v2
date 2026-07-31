from __future__ import annotations

from unittest.mock import MagicMock

import pyodbc
import pytest
from sqlalchemy import Connection
from sqlalchemy.pool import NullPool

from auto_trading_v2.adapters.persistence.administration import (
    MssqlAdministrationEngineFactory,
    MssqlAdministrationErrorCategory,
    MssqlAdministrationSafetyError,
    verify_local_shared_memory_connection,
)
from auto_trading_v2.adapters.persistence.database_admin import DatabaseSafetyError
from auto_trading_v2.config import (
    MssqlAdministrationSettings,
    MssqlAdministrationTransport,
    SecretValue,
)

LOCAL_INTEGRATED_URL = (
    "mssql+pyodbc://@localhost/master?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes"
)
TCP_URL = "mssql+pyodbc://admin:password@localhost/master?driver=ODBC+Driver+18+for+SQL+Server"


def _settings(
    *,
    url: str = LOCAL_INTEGRATED_URL,
    transport: MssqlAdministrationTransport = (MssqlAdministrationTransport.LOCAL_SHARED_MEMORY),
) -> MssqlAdministrationSettings:
    return MssqlAdministrationSettings(
        admin_url=SecretValue(url),
        test_admin_url=None,
        admin_transport=transport,
    )


def test_tcp_url_mode_preserves_existing_database_url_behavior() -> None:
    factory = MssqlAdministrationEngineFactory(
        _settings(url=TCP_URL, transport=MssqlAdministrationTransport.TCP_URL)
    )
    master = factory.create_master_engine()
    target = factory.create_target_engine("auto_trading_v2_test_tcp")
    try:
        assert master.url.database == "master"
        assert target.url.database == "auto_trading_v2_test_tcp"
        assert master.hide_parameters is True
        assert target.hide_parameters is True
    finally:
        target.dispose()
        master.dispose()


def test_lpc_engine_is_unconnected_redacted_and_uses_null_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_connected(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("engine construction must not connect")

    monkeypatch.setattr(pyodbc, "connect", fail_if_connected)
    factory = MssqlAdministrationEngineFactory(_settings())
    master = factory.create_master_engine()
    target = factory.create_target_engine("auto_trading_v2_test_lpc")
    try:
        assert isinstance(master.pool, NullPool)
        assert isinstance(target.pool, NullPool)
        assert master.hide_parameters is True
        assert target.hide_parameters is True
        assert master.url.host is None
        assert master.url.username is None
        assert master.url.password is None
        assert "lpc:" not in repr(master)
        assert "localhost" not in repr(factory)
    finally:
        target.dispose()
        master.dispose()


def test_lpc_creator_builds_integrated_local_contract_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_connect(connection_string: str, **kwargs: object) -> object:
        captured["connection_string"] = connection_string
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(pyodbc, "connect", fake_connect)
    engine = MssqlAdministrationEngineFactory(_settings()).create_master_engine()
    try:
        assert engine.pool._creator() is sentinel  # type: ignore[attr-defined]
        connection_string = str(captured["connection_string"])
        assert "SERVER=lpc:(local)" in connection_string
        assert "DATABASE=master" in connection_string
        assert "Trusted_Connection=yes" in connection_string
        assert "ODBC Driver 18 for SQL Server" in connection_string
        assert "UID=" not in connection_string
        assert "PWD=" not in connection_string
        assert "tcp:" not in connection_string.casefold()
        assert captured["kwargs"] == {"autocommit": True}
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("url", "category"),
    [
        (
            "mssql+pyodbc://@remote.example/master?"
            "driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes",
            MssqlAdministrationErrorCategory.LPC_REMOTE_ENDPOINT,
        ),
        (
            "mssql+pyodbc://user:password@localhost/master?"
            "driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes",
            MssqlAdministrationErrorCategory.LPC_CREDENTIALS_PRESENT,
        ),
        (
            "mssql+pyodbc://@localhost/master?"
            "driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes",
            MssqlAdministrationErrorCategory.LPC_DRIVER_UNSUPPORTED,
        ),
        (
            "mssql+pyodbc://@localhost/master?"
            "driver=ODBC+Driver+18+for+SQL+Server&uid=user&Trusted_Connection=yes",
            MssqlAdministrationErrorCategory.LPC_SQL_AUTH_MIXED,
        ),
        (
            "mssql+pyodbc://@localhost/master?"
            "driver=ODBC+Driver+18+for+SQL+Server&dsn=local&Trusted_Connection=yes",
            MssqlAdministrationErrorCategory.LPC_DSN_UNSUPPORTED,
        ),
        (
            "mssql+pyodbc://@localhost/master?driver=ODBC+Driver+18+for+SQL+Server",
            MssqlAdministrationErrorCategory.LPC_INTEGRATED_AUTH_REQUIRED,
        ),
    ],
)
def test_unsafe_lpc_configuration_is_rejected_without_fallback(
    url: str,
    category: MssqlAdministrationErrorCategory,
) -> None:
    with pytest.raises(MssqlAdministrationSafetyError) as caught:
        MssqlAdministrationEngineFactory(_settings(url=url)).create_master_engine()

    assert caught.value.category is category
    assert "remote.example" not in str(caught.value)
    assert "password" not in str(caught.value)


def test_non_master_and_invalid_target_are_rejected_before_connection() -> None:
    non_master = LOCAL_INTEGRATED_URL.replace("/master?", "/other?")
    with pytest.raises(MssqlAdministrationSafetyError) as caught:
        MssqlAdministrationEngineFactory(_settings(url=non_master)).create_master_engine()
    assert caught.value.category is MssqlAdministrationErrorCategory.LPC_DATABASE_NOT_MASTER

    with pytest.raises(DatabaseSafetyError):
        MssqlAdministrationEngineFactory(_settings()).create_target_engine("auto_trading_v2")


def test_verify_lpc_connection_returns_only_safe_facts() -> None:
    connection = MagicMock(spec=Connection)
    connection.exec_driver_sql.return_value.mappings.return_value.one.return_value = {
        "database_name": "master",
        "net_transport": "Shared memory",
        "auth_scheme": "NTLM",
        "can_create_database": 1,
        "can_alter_database": 1,
    }

    info = verify_local_shared_memory_connection(
        connection,
        expected_database="master",
        require_admin_permissions=True,
    )

    assert info.database_matches
    assert info.shared_memory
    assert info.integrated_auth
    assert info.auth_scheme == "NTLM"
    assert info.can_create_database
    assert info.can_alter_database


@pytest.mark.parametrize(
    ("field", "value", "category"),
    [
        (
            "database_name",
            "wrong",
            MssqlAdministrationErrorCategory.LPC_DATABASE_MISMATCH,
        ),
        (
            "net_transport",
            "TCP",
            MssqlAdministrationErrorCategory.LPC_TRANSPORT_MISMATCH,
        ),
        (
            "auth_scheme",
            "SQL",
            MssqlAdministrationErrorCategory.LPC_AUTH_MISMATCH,
        ),
        (
            "can_create_database",
            0,
            MssqlAdministrationErrorCategory.LPC_PERMISSION_INSUFFICIENT,
        ),
    ],
)
def test_lpc_connection_mismatch_is_safely_categorized(
    field: str,
    value: object,
    category: MssqlAdministrationErrorCategory,
) -> None:
    row = {
        "database_name": "master",
        "net_transport": "Shared memory",
        "auth_scheme": "KERBEROS",
        "can_create_database": 1,
        "can_alter_database": 1,
    }
    row[field] = value
    connection = MagicMock(spec=Connection)
    connection.exec_driver_sql.return_value.mappings.return_value.one.return_value = row

    with pytest.raises(MssqlAdministrationSafetyError) as caught:
        verify_local_shared_memory_connection(
            connection,
            expected_database="master",
            require_admin_permissions=True,
        )

    assert caught.value.category is category
