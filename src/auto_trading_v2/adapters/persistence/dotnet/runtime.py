"""Lazy, explicit pythonnet netfx and System.Data.SqlClient loader."""

from __future__ import annotations

import importlib
import struct
from dataclasses import dataclass
from threading import Lock
from typing import Any

from auto_trading_v2.adapters.persistence.dotnet.errors import DotNetRuntimeError


@dataclass(frozen=True, slots=True)
class DotNetRuntimeInfo:
    provider: str
    runtime_kind: str
    runtime_version: str
    process_bitness: int


@dataclass(frozen=True, slots=True, repr=False)
class DotNetBindings:
    runtime_info: DotNetRuntimeInfo
    sql_connection: Any
    sql_connection_string_builder: Any
    sql_db_type: Any
    db_null: Any
    net_boolean: Any
    net_date_time: Any
    net_date_time_kind: Any
    net_date_time_offset: Any
    net_decimal: Any
    net_guid: Any
    net_int32: Any
    net_int64: Any
    invariant_culture: Any


_lock = Lock()
_bindings: DotNetBindings | None = None


def _runtime_kind(info: object | None) -> str:
    if info is None:
        return ""
    return str(getattr(info, "kind", ""))


def _is_netfx(kind: str) -> bool:
    normalized = kind.casefold()
    return normalized in {"netfx", ".net framework"}


def _load_bindings() -> DotNetBindings:
    stage = "PYTHONNET_IMPORT"
    try:
        pythonnet = importlib.import_module("pythonnet")
        current_info = pythonnet.get_runtime_info()
        stage = "NETFX_LOAD"
        if current_info is not None and not _is_netfx(_runtime_kind(current_info)):
            raise RuntimeError("a different CLR runtime is already loaded")
        if current_info is None:
            pythonnet.load("netfx")

        stage = "CLR_IMPORT"
        clr = importlib.import_module("clr")
        stage = "SYSTEM_DATA_LOAD"
        clr.AddReference("System.Data")

        system = importlib.import_module("System")
        system_data = importlib.import_module("System.Data")
        globalization = importlib.import_module("System.Globalization")
        sqlclient = importlib.import_module("System.Data.SqlClient")
        stage = "SQLCLIENT_IMPORT"
        connection_type = sqlclient.SqlConnection
        builder_type = sqlclient.SqlConnectionStringBuilder

        loaded_info = pythonnet.get_runtime_info()
        kind = _runtime_kind(loaded_info) or ".NET Framework"
        version = str(system.Environment.Version)
        info = DotNetRuntimeInfo(
            provider="dotnet",
            runtime_kind=kind,
            runtime_version=version,
            process_bitness=struct.calcsize("P") * 8,
        )
        return DotNetBindings(
            runtime_info=info,
            sql_connection=connection_type,
            sql_connection_string_builder=builder_type,
            sql_db_type=system_data.SqlDbType,
            db_null=system.DBNull,
            net_boolean=system.Boolean,
            net_date_time=system.DateTime,
            net_date_time_kind=system.DateTimeKind,
            net_date_time_offset=system.DateTimeOffset,
            net_decimal=system.Decimal,
            net_guid=system.Guid,
            net_int32=system.Int32,
            net_int64=system.Int64,
            invariant_culture=globalization.CultureInfo.InvariantCulture,
        )
    except DotNetRuntimeError:
        raise
    except Exception as exc:
        raise DotNetRuntimeError(stage, type(exc).__name__) from None


def get_sqlclient_bindings() -> DotNetBindings:
    """Load netfx exactly once and return safe-to-cache type bindings."""

    global _bindings
    if _bindings is not None:
        return _bindings
    with _lock:
        if _bindings is None:
            _bindings = _load_bindings()
        return _bindings


def load_sqlclient_runtime() -> DotNetRuntimeInfo:
    """Explicitly initialize System.Data.SqlClient and return sanitized runtime facts."""

    return get_sqlclient_bindings().runtime_info
