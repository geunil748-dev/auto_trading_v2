"""Immutable rows and explicit DotNet-to-Python result conversion."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, overload
from uuid import UUID

from auto_trading_v2.adapters.persistence.dotnet.errors import DotNetResultConversionError
from auto_trading_v2.adapters.persistence.dotnet.runtime import (
    DotNetBindings,
    get_sqlclient_bindings,
)


@dataclass(frozen=True, slots=True)
class DotNetRow(Mapping[str, object]):
    columns: tuple[str, ...]
    cells: tuple[object, ...]

    def __post_init__(self) -> None:
        if len(self.columns) != len(self.cells):
            raise ValueError("row column/value length mismatch")
        folded = tuple(column.casefold() for column in self.columns)
        if len(set(folded)) != len(folded):
            raise ValueError("duplicate result column names are not allowed")

    @overload
    def __getitem__(self, key: str) -> object: ...

    @overload
    def __getitem__(self, key: int) -> object: ...

    def __getitem__(self, key: str | int) -> object:
        if isinstance(key, int):
            return self.cells[key]
        folded = key.casefold()
        for index, column in enumerate(self.columns):
            if column.casefold() == folded:
                return self.cells[index]
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.columns)

    def __len__(self) -> int:
        return len(self.columns)

    def as_tuple(self) -> tuple[object, ...]:
        return self.cells


@dataclass(frozen=True, slots=True)
class DotNetRows(Sequence[DotNetRow]):
    columns: tuple[str, ...]
    rows: tuple[DotNetRow, ...]

    @overload
    def __getitem__(self, index: int) -> DotNetRow: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[DotNetRow]: ...

    def __getitem__(self, index: int | slice) -> DotNetRow | Sequence[DotNetRow]:
        return self.rows[index]

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def rowcount(self) -> int:
        return len(self.rows)


def _dotnet_type_name(value: object) -> str:
    try:
        net_type = value.GetType()  # type: ignore[attr-defined]
        return str(net_type.FullName)
    except (AttributeError, TypeError):
        return ""


def _datetime_from_ticks(ticks: int) -> datetime:
    return datetime(1, 1, 1, tzinfo=UTC) + timedelta(microseconds=ticks // 10)


def convert_dotnet_value(
    value: object,
    *,
    bindings: DotNetBindings | None = None,
    data_type_name: str = "",
) -> object:
    """Convert an approved SqlClient value without float-based time or decimal paths."""

    if value is None or isinstance(value, (bool, int, str, Decimal, UUID, date)):
        if isinstance(value, datetime) and value.tzinfo is None:
            raise DotNetResultConversionError("naive datetime results are not allowed")
        return value
    resolved = get_sqlclient_bindings() if bindings is None else bindings
    type_name = _dotnet_type_name(value)
    dynamic: Any = value
    if type_name == "System.DBNull":
        return None
    if type_name == "System.Decimal":
        rendered = str(dynamic.ToString(resolved.invariant_culture))
        return Decimal(rendered)
    if type_name == "System.Guid":
        return UUID(str(dynamic.ToString()))
    if type_name == "System.DateTimeOffset":
        return _datetime_from_ticks(int(dynamic.UtcDateTime.Ticks))
    if type_name == "System.DateTime":
        if data_type_name.casefold() == "date":
            return date(int(dynamic.Year), int(dynamic.Month), int(dynamic.Day))
        raise DotNetResultConversionError("System.DateTime results require an explicit policy")
    if type_name in {"System.Int16", "System.Int32", "System.Int64", "System.Byte"}:
        return int(dynamic)
    if type_name == "System.Boolean":
        return bool(dynamic)
    if type_name in {"System.String", "System.Char"}:
        return str(dynamic)
    raise DotNetResultConversionError("unsupported DotNet result type")
