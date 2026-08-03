import re

from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex, CreateTable

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES


def _compiled_ddl() -> str:
    dialect = mssql.dialect()
    statements = [str(CreateTable(table).compile(dialect=dialect)) for table in BUSINESS_TABLES]
    statements.extend(
        str(CreateIndex(index).compile(dialect=dialect))
        for table in BUSINESS_TABLES
        for index in table.indexes
    )
    return "\n".join(statements)


def test_metadata_compiles_to_mssql_canonical_types() -> None:
    ddl = _compiled_ddl()

    assert "UNIQUEIDENTIFIER" in ddl
    assert "DATETIMEOFFSET(7)" in ddl
    assert "DECIMAL(38, 18)" in ddl
    assert "NVARCHAR(max)" in ddl
    assert " BIT " in ddl
    assert "trading." in ddl


def test_compiled_ddl_has_no_wrong_database_types_or_batch_commands() -> None:
    ddl = _compiled_ddl()

    for forbidden in (r"\bFLOAT\b", r"\bREAL\b", r"\bMONEY\b", r"\bSMALLMONEY\b"):
        assert re.search(forbidden, ddl, flags=re.IGNORECASE) is None
    assert "CREATE DATABASE" not in ddl.upper()
    assert re.search(r"(?m)^\s*GO\s*$", ddl, flags=re.IGNORECASE) is None
    assert "JSONB" not in ddl.upper()
    assert "POSTGRES" not in ddl.upper()


def test_filtered_indexes_compile_with_where_clauses() -> None:
    ddl = _compiled_ddl()

    assert "WHERE status = 'OPEN'" in ddl
    assert "WHERE candidate_id IS NOT NULL" in ddl
    assert "WHERE position_id IS NOT NULL" in ddl
    assert "WHERE broker_order_ref IS NOT NULL" in ddl
    assert "ISJSON(details) = 1" in ddl
    assert "ISJSON(payload) = 1" in ddl
    assert "ISJSON(feature_values) = 1" in ddl
    assert "ISJSON(provenance) = 1" in ddl
    assert "FOREIGN KEY(position_id, position_version)" in ddl
    assert "REFERENCES trading.position_events (position_id, sequence_no)" in ddl
