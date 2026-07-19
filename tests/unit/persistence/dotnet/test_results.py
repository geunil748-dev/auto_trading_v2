from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from auto_trading_v2.adapters.persistence.dotnet.errors import DotNetResultConversionError
from auto_trading_v2.adapters.persistence.dotnet.results import (
    DotNetRow,
    DotNetRows,
    convert_dotnet_value,
)
from auto_trading_v2.adapters.persistence.dotnet.runtime import DotNetBindings


class FakeNetValue:
    def __init__(self, type_name: str, value: object) -> None:
        self._type_name = type_name
        self.value = value

    def GetType(self) -> object:
        return SimpleNamespace(FullName=self._type_name)

    def ToString(self, *args: object) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return int(cast(int, self.value))

    def __bool__(self) -> bool:
        return bool(self.value)


def _bindings() -> DotNetBindings:
    return cast(DotNetBindings, SimpleNamespace(invariant_culture="invariant"))


def test_row_is_immutable_mapping_with_deterministic_order() -> None:
    row = DotNetRow(("Number", "Label"), (1, "one"))
    rows = DotNetRows(row.columns, (row,))

    assert tuple(row) == ("Number", "Label")
    assert row[0] == 1
    assert row["number"] == 1
    assert row.as_tuple() == (1, "one")
    assert rows.rowcount == 1
    with pytest.raises(ValueError, match="duplicate"):
        DotNetRow(("value", "VALUE"), (1, 2))


def test_decimal_guid_and_primitives_convert_without_float_paths() -> None:
    decimal_value = FakeNetValue("System.Decimal", "123.450000000000000000")
    guid_text = "12345678-1234-5678-1234-567812345678"
    guid_value = FakeNetValue("System.Guid", guid_text)

    assert convert_dotnet_value(decimal_value, bindings=_bindings()) == Decimal(
        "123.450000000000000000"
    )
    assert convert_dotnet_value(guid_value, bindings=_bindings()) == UUID(guid_text)
    assert convert_dotnet_value(FakeNetValue("System.Int64", 7), bindings=_bindings()) == 7
    assert convert_dotnet_value(FakeNetValue("System.Boolean", True), bindings=_bindings()) is True
    assert (
        convert_dotnet_value(FakeNetValue("System.String", "한글"), bindings=_bindings()) == "한글"
    )
    assert convert_dotnet_value(FakeNetValue("System.DBNull", None), bindings=_bindings()) is None


def test_datetimeoffset_uses_integer_ticks_and_returns_utc() -> None:
    ticks_per_day = 24 * 60 * 60 * 10_000_000
    ticks = 638_000 * ticks_per_day + 1_234_567
    value = FakeNetValue("System.DateTimeOffset", None)
    value.UtcDateTime = SimpleNamespace(Ticks=ticks)

    converted = convert_dotnet_value(value, bindings=_bindings())

    assert isinstance(converted, datetime)
    assert converted.tzinfo is UTC
    assert converted.microsecond == 123456


def test_system_datetime_and_unknown_types_are_rejected() -> None:
    with pytest.raises(DotNetResultConversionError):
        convert_dotnet_value(FakeNetValue("System.DateTime", None), bindings=_bindings())
    with pytest.raises(DotNetResultConversionError):
        convert_dotnet_value(FakeNetValue("Private.Type", "secret"), bindings=_bindings())


def test_system_datetime_is_converted_only_for_an_explicit_sql_date_column() -> None:
    value = FakeNetValue("System.DateTime", None)
    value.Year = 2026
    value.Month = 7
    value.Day = 19

    assert convert_dotnet_value(
        value,
        bindings=_bindings(),
        data_type_name="date",
    ) == date(2026, 7, 19)
