"""Alembic bookkeeping table contract for explicit long revision identifiers."""

from __future__ import annotations

from typing import Any

from alembic.ddl.mssql import MSSQLImpl
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table

VERSION_NUM_LENGTH = 64


class V2MssqlImpl(MSSQLImpl):
    """Keep Alembic revision storage wider than the frozen P3 identifier."""

    __dialect__ = "mssql"

    def version_table_impl(
        self,
        *,
        version_table: str,
        version_table_schema: str | None,
        version_table_pk: bool,
        **kw: Any,
    ) -> Table:
        del kw
        table = Table(
            version_table,
            MetaData(),
            Column("version_num", String(VERSION_NUM_LENGTH), nullable=False),
            schema=version_table_schema,
        )
        if version_table_pk:
            table.append_constraint(
                PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
            )
        return table
