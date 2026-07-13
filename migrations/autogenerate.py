"""MSSQL-aware Alembic autogenerate comparison policy."""

from __future__ import annotations

from typing import Any


def include_schema_object(
    _object: object,
    name: str | None,
    object_type: str,
    _reflected: bool,
    _compare_to: object | None,
) -> bool:
    """Exclude Alembic's internal version table from business schema drift."""

    return not (object_type == "table" and name == "alembic_version")


def compare_mssql_server_default(
    _context: object,
    inspected_column: Any,
    _metadata_column: object,
    inspected_default: str | None,
    _metadata_default: object | None,
    rendered_metadata_default: str | None,
) -> bool | None:
    """Treat SQL Server's wrapping parentheses as equivalent for UTC defaults."""

    if inspected_column.name != "recorded_at":
        return None
    if inspected_default is None or rendered_metadata_default is None:
        return None
    return _normalize_default(inspected_default) != _normalize_default(rendered_metadata_default)


def _normalize_default(value: str) -> str:
    normalized = "".join(value.split()).casefold()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]
    return normalized
