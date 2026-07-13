from types import SimpleNamespace

from migrations.autogenerate import (
    compare_mssql_server_default,
    include_schema_object,
)


def test_internal_alembic_version_table_is_excluded_from_drift() -> None:
    assert include_schema_object(object(), "alembic_version", "table", True, None) is False
    assert include_schema_object(object(), "market_snapshots", "table", True, None) is True


def test_mssql_utc_default_parentheses_are_semantically_equivalent() -> None:
    inspected_column = SimpleNamespace(name="recorded_at")

    result = compare_mssql_server_default(
        object(),
        inspected_column,
        object(),
        "(todatetimeoffset(sysutcdatetime(),'+00:00'))",
        object(),
        "TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00')",
    )

    assert result is False


def test_mssql_different_recorded_at_default_is_reported_as_drift() -> None:
    inspected_column = SimpleNamespace(name="recorded_at")

    result = compare_mssql_server_default(
        object(),
        inspected_column,
        object(),
        "(getdate())",
        object(),
        "TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00')",
    )

    assert result is True


def test_non_recorded_at_defaults_use_alembic_dialect_comparison() -> None:
    inspected_column = SimpleNamespace(name="other_column")

    result = compare_mssql_server_default(
        object(),
        inspected_column,
        object(),
        "(1)",
        object(),
        "1",
    )

    assert result is None
