from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast

from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    DotNetPersistenceError,
)
from auto_trading_v2.adapters.persistence.dotnet.results import DotNetRow, DotNetRows
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings


class FakeFactory:
    def __init__(self, settings: DotNetDatabaseSettings) -> None:
        self.settings = settings

    @contextmanager
    def opened_connection(self) -> Iterator[object]:
        yield object()


class PassingExecutor:
    def execute_scalar(self, connection: object, sql: str, **kwargs: object) -> int:
        return 1

    def execute_rows(self, connection: object, sql: str, **kwargs: object) -> DotNetRows:
        assert "CONNECTIONPROPERTY" in sql
        assert "sys.dm_exec_connections" not in sql
        columns = ("net_transport", "protocol_type", "auth_scheme")
        row = DotNetRow(columns, ("TCP", "TSQL", "SQL"))
        return DotNetRows(columns, (row,))


class TimeoutExecutor(PassingExecutor):
    def execute_scalar(self, connection: object, sql: str, **kwargs: object) -> int:
        raise DotNetPersistenceError(
            operation="execute_scalar",
            category=DotNetErrorCategory.TIMEOUT,
            number=-2,
        )


class UnexpectedFailureExecutor(PassingExecutor):
    def execute_scalar(self, connection: object, sql: str, **kwargs: object) -> int:
        raise RuntimeError("raw server and credential details")


class OptionalMetadataFailureExecutor(PassingExecutor):
    def execute_rows(self, connection: object, sql: str, **kwargs: object) -> DotNetRows:
        raise DotNetPersistenceError(
            operation="execute_rows",
            category=DotNetErrorCategory.CONSTRAINT_VIOLATION,
            number=547,
        )


class FakeTransaction:
    rolled_back = False

    def __init__(self, connection: object) -> None:
        self.connection = connection
        self.raw_transaction = object()

    def __enter__(self) -> FakeTransaction:
        return self

    def rollback(self) -> None:
        type(self).rolled_back = True

    def __exit__(self, *args: object) -> None:
        return None


def _settings() -> DotNetDatabaseSettings:
    return cast(
        DotNetDatabaseSettings,
        SimpleNamespace(encrypt=False, trust_server_certificate=True),
    )


def _patch_common(monkeypatch: object) -> None:
    patcher = cast(object, monkeypatch)
    patcher.setattr(  # type: ignore[attr-defined]
        "auto_trading_v2.adapters.persistence.dotnet.probe.load_sqlclient_runtime",
        lambda: SimpleNamespace(runtime_kind=".NET Framework", process_bitness=64),
    )
    patcher.setattr(  # type: ignore[attr-defined]
        "auto_trading_v2.adapters.persistence.dotnet.probe.DotNetConnectionFactory",
        FakeFactory,
    )


def test_read_only_probe_returns_only_sanitized_connection_facts(monkeypatch: object) -> None:
    from auto_trading_v2.adapters.persistence.dotnet import probe as probe_module

    _patch_common(monkeypatch)
    cast(object, monkeypatch).setattr(  # type: ignore[attr-defined]
        probe_module,
        "DotNetCommandExecutor",
        PassingExecutor,
    )

    result = probe_module.run_read_only_probe(_settings())

    assert result.status == "PASS"
    assert result.provider == "dotnet"
    assert result.net_transport == "TCP"
    assert result.protocol_type == "TSQL"
    assert result.auth_scheme == "SQL"
    assert result.select_one_status == "PASS"
    assert result.metadata_status == "PASS"
    assert result.requested_encrypt is False
    assert result.requested_trust_server_certificate is True
    assert "host" not in repr(result).casefold()


def test_probe_failure_keeps_only_safe_category(monkeypatch: object) -> None:
    from auto_trading_v2.adapters.persistence.dotnet import probe as probe_module

    _patch_common(monkeypatch)
    cast(object, monkeypatch).setattr(  # type: ignore[attr-defined]
        probe_module,
        "DotNetCommandExecutor",
        TimeoutExecutor,
    )

    result = probe_module.run_read_only_probe(_settings())

    assert result.status == "FAIL"
    assert result.failure_stage == "SELECT_1"
    assert result.safe_error_category == "TIMEOUT"


def test_unexpected_probe_failure_is_sanitized(monkeypatch: object) -> None:
    from auto_trading_v2.adapters.persistence.dotnet import probe as probe_module

    _patch_common(monkeypatch)
    cast(object, monkeypatch).setattr(  # type: ignore[attr-defined]
        probe_module,
        "DotNetCommandExecutor",
        UnexpectedFailureExecutor,
    )

    result = probe_module.run_read_only_probe(_settings())

    assert result.status == "FAIL"
    assert result.failure_stage == "SELECT_1"
    assert result.safe_error_category == "UNKNOWN"
    assert "credential" not in repr(result).casefold()


def test_optional_metadata_failure_does_not_reverse_select_one(monkeypatch: object) -> None:
    from auto_trading_v2.adapters.persistence.dotnet import probe as probe_module

    _patch_common(monkeypatch)
    cast(object, monkeypatch).setattr(  # type: ignore[attr-defined]
        probe_module,
        "DotNetCommandExecutor",
        OptionalMetadataFailureExecutor,
    )

    result = probe_module.run_read_only_probe(_settings())

    assert result.status == "PASS"
    assert result.select_one_status == "PASS"
    assert result.metadata_status == "OPTIONAL_DIAGNOSTIC_UNAVAILABLE"
    assert result.metadata_safe_error_category == "CONSTRAINT_VIOLATION"
    assert result.net_transport is None


def test_transaction_smoke_uses_explicit_rollback(monkeypatch: object) -> None:
    from auto_trading_v2.adapters.persistence.dotnet import probe as probe_module

    _patch_common(monkeypatch)
    FakeTransaction.rolled_back = False
    cast(object, monkeypatch).setattr(  # type: ignore[attr-defined]
        probe_module,
        "DotNetCommandExecutor",
        PassingExecutor,
    )
    cast(object, monkeypatch).setattr(  # type: ignore[attr-defined]
        probe_module,
        "DotNetTransaction",
        FakeTransaction,
    )

    result = probe_module.run_transaction_rollback_smoke(_settings())

    assert result.status == "PASS"
    assert FakeTransaction.rolled_back is True
