from sqlalchemy import Float, Numeric
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES

EXPECTED_TABLES = {
    "market_snapshots",
    "daily_market_bars",
    "candidates",
    "filter_evaluations",
    "feature_snapshots",
    "recommendations",
    "strategy_decisions",
    "trade_intents",
    "paper_orders",
    "paper_fills",
    "paper_positions",
    "position_events",
    "equity_snapshots",
    "trading_events",
    "universe_snapshots",
    "daily_feature_pipeline_runs",
    "daily_feature_pipeline_items",
}


def test_business_table_registry_is_exact_and_schema_qualified() -> None:
    assert len(BUSINESS_TABLES) == 17
    assert {table.name for table in BUSINESS_TABLES} == EXPECTED_TABLES
    assert {table.schema for table in BUSINESS_TABLES} == {"trading"}


def test_all_primary_keys_and_id_columns_use_uniqueidentifier() -> None:
    for table in BUSINESS_TABLES:
        assert len(table.primary_key.columns) == 1
        assert table.primary_key.name == f"pk_{table.name}"
        for column in table.columns:
            if column.name.endswith("_id"):
                assert isinstance(column.type, mssql.UNIQUEIDENTIFIER), (table.name, column.name)


def test_all_official_decimals_are_fixed_precision_and_no_float_types_exist() -> None:
    decimal_columns = []
    for table in BUSINESS_TABLES:
        for column in table.columns:
            assert not isinstance(column.type, Float), (table.name, column.name)
            if isinstance(column.type, Numeric):
                decimal_columns.append((table.name, column.name))
                assert column.type.precision == 38
                assert column.type.scale == 18
                assert column.type.asdecimal is True

    assert decimal_columns


def test_all_datetime_columns_use_datetimeoffset_7() -> None:
    datetime_columns = []
    for table in BUSINESS_TABLES:
        for column in table.columns:
            if column.name.endswith("_at") or column.name == "as_of":
                datetime_columns.append((table.name, column.name))
                assert isinstance(column.type, mssql.DATETIMEOFFSET)
                assert column.type.precision == 7

    assert datetime_columns


def test_every_table_has_utc_recorded_at_default() -> None:
    for table in BUSINESS_TABLES:
        recorded_at = table.c.recorded_at
        assert recorded_at.nullable is False
        assert isinstance(recorded_at.type, mssql.DATETIMEOFFSET)
        assert recorded_at.server_default is not None
        assert "TODATETIMEOFFSET(SYSUTCDATETIME(), '+00:00')" in str(recorded_at.server_default.arg)


def test_foreign_keys_are_no_action_and_all_objects_are_explicitly_named() -> None:
    for table in BUSINESS_TABLES:
        for foreign_key in table.foreign_key_constraints:
            assert foreign_key.ondelete == "NO ACTION"
            assert foreign_key.name
            assert len(foreign_key.name) <= 128
        for constraint in table.constraints:
            assert constraint.name
            assert len(constraint.name) <= 128
        for index in table.indexes:
            assert index.name
            assert len(index.name) <= 128


def test_index_keys_stay_below_sql_server_900_byte_limit() -> None:
    for table in BUSINESS_TABLES:
        for index in table.indexes:
            estimated_bytes = 0
            for expression in index.expressions:
                length = getattr(expression.type, "length", None)
                if length is not None:
                    estimated_bytes += int(length) * (
                        2 if isinstance(expression.type, mssql.NVARCHAR) else 1
                    )
                elif isinstance(expression.type, mssql.UNIQUEIDENTIFIER):
                    estimated_bytes += 16
                else:
                    estimated_bytes += 16
            assert estimated_bytes <= 900, index.name
