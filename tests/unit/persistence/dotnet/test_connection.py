from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from auto_trading_v2.adapters.persistence.dotnet.connection import DotNetConnectionFactory
from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    DotNetPersistenceError,
)
from auto_trading_v2.adapters.persistence.dotnet.runtime import DotNetBindings
from auto_trading_v2.config import SecretValue
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings

SENTINEL = "CONNECTION_SECRET_30ad1e"


class FakeBuilder:
    last: FakeBuilder | None = None

    def __init__(self) -> None:
        type(self).last = self
        self.ConnectionString = f"Password={SENTINEL}"


class FakeConnection:
    last: FakeConnection | None = None
    fail_open = False

    def __init__(self, connection_string: str) -> None:
        type(self).last = self
        self.connection_string = connection_string
        self.opened = False
        self.closed = False
        self.disposed = False

    def Open(self) -> None:
        if self.fail_open:
            error = RuntimeError(SENTINEL)
            error.Number = 18456  # type: ignore[attr-defined]
            raise error
        self.opened = True

    def Close(self) -> None:
        self.closed = True

    def Dispose(self) -> None:
        self.disposed = True


def _settings() -> DotNetDatabaseSettings:
    return DotNetDatabaseSettings(
        provider="dotnet",
        environment="development",
        host="localhost",
        port=1433,
        database="auto_trading_v2",
        username=SecretValue(f"user_{SENTINEL}"),
        password=SecretValue(SENTINEL),
        encrypt=False,
        trust_server_certificate=True,
        connect_timeout=5,
    )


def _bindings() -> DotNetBindings:
    return cast(
        DotNetBindings,
        SimpleNamespace(
            sql_connection_string_builder=FakeBuilder,
            sql_connection=FakeConnection,
        ),
    )


def test_builder_uses_explicit_safe_properties_and_fresh_connection() -> None:
    factory = DotNetConnectionFactory(_settings(), _bindings)

    first = factory.create_connection()
    second = factory.create_connection()
    builder = FakeBuilder.last

    assert first is not second
    assert builder is not None
    assert builder.DataSource == "tcp:localhost,1433"
    assert builder.InitialCatalog == "auto_trading_v2"
    assert builder.UserID.endswith(SENTINEL)
    assert builder.Password == SENTINEL
    assert builder.IntegratedSecurity is False
    assert builder.Encrypt is False
    assert builder.TrustServerCertificate is True
    assert builder.ConnectTimeout == 5
    assert builder.PersistSecurityInfo is False
    assert builder.ApplicationName == "auto_trading_v2"
    assert builder.MultipleActiveResultSets is False
    assert SENTINEL not in repr(factory)


def test_opened_connection_closes_and_disposes() -> None:
    factory = DotNetConnectionFactory(_settings(), _bindings)

    with factory.opened_connection() as connection:
        assert cast(FakeConnection, connection).opened is True

    resolved = cast(FakeConnection, connection)
    assert resolved.closed is True
    assert resolved.disposed is True


def test_open_failure_is_classified_without_raw_message() -> None:
    factory = DotNetConnectionFactory(_settings(), _bindings)
    FakeConnection.fail_open = True
    try:
        with pytest.raises(DotNetPersistenceError) as caught:
            factory.open_connection()
    finally:
        FakeConnection.fail_open = False

    assert caught.value.category is DotNetErrorCategory.AUTHENTICATION
    assert SENTINEL not in str(caught.value)
    assert FakeConnection.last is not None
    assert FakeConnection.last.disposed is True
