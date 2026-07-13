import pytest
from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint, inspect, text
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES

pytestmark = pytest.mark.integration


def test_migration_revision_catalog_and_drift(mssql_database: object) -> None:
    expected = {table.name for table in BUSINESS_TABLES}
    inspector = inspect(mssql_database.engine)
    assert set(inspector.get_table_names(schema="trading")) == expected
    with mssql_database.engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM dbo.alembic_version")
        ).scalar_one()
    assert revision == "0001_mssql_schema"
    mssql_database.run_check()


def test_downgrade_and_reupgrade_only_temporary_database(mssql_database: object) -> None:
    assert mssql_database.name.startswith("auto_trading_v2_test_")

    mssql_database.run_downgrade("base")
    inspector = inspect(mssql_database.engine)
    assert inspector.get_table_names(schema="trading") == []

    mssql_database.run_upgrade("head")
    assert len(inspect(mssql_database.engine).get_table_names(schema="trading")) == 11
    mssql_database.run_check()


def test_sql_server_catalog_contract(mssql_database: object) -> None:
    expected_fk_count = sum(len(table.foreign_key_constraints) for table in BUSINESS_TABLES)
    expected_check_count = sum(
        sum(isinstance(constraint, CheckConstraint) for constraint in table.constraints)
        for table in BUSINESS_TABLES
    )
    expected_unique_count = sum(
        sum(isinstance(constraint, UniqueConstraint) for constraint in table.constraints)
        for table in BUSINESS_TABLES
    )
    expected_decimal_count = sum(
        sum(isinstance(column.type, Numeric) for column in table.columns)
        for table in BUSINESS_TABLES
    )
    expected_datetime_count = sum(
        sum(isinstance(column.type, mssql.DATETIMEOFFSET) for column in table.columns)
        for table in BUSINESS_TABLES
    )
    expected_uuid_count = sum(
        sum(isinstance(column.type, mssql.UNIQUEIDENTIFIER) for column in table.columns)
        for table in BUSINESS_TABLES
    )

    with mssql_database.engine.connect() as connection:
        table_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s "
                "ON t.schema_id = s.schema_id WHERE s.name = 'trading'"
            )
        ).scalar_one()
        pk_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM sys.key_constraints kc JOIN sys.tables t "
                "ON kc.parent_object_id = t.object_id JOIN sys.schemas s "
                "ON t.schema_id = s.schema_id WHERE s.name = 'trading' AND kc.type = 'PK'"
            )
        ).scalar_one()
        wrong_delete_actions = connection.execute(
            text(
                "SELECT COUNT(*) FROM sys.foreign_keys fk JOIN sys.tables t "
                "ON fk.parent_object_id = t.object_id JOIN sys.schemas s "
                "ON t.schema_id = s.schema_id WHERE s.name = 'trading' "
                "AND fk.delete_referential_action_desc <> 'NO_ACTION'"
            )
        ).scalar_one()
        filtered_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM sys.indexes i JOIN sys.tables t "
                "ON i.object_id = t.object_id JOIN sys.schemas s "
                "ON t.schema_id = s.schema_id WHERE s.name = 'trading' AND i.has_filter = 1"
            )
        ).scalar_one()
        constraint_counts = (
            connection.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM sys.foreign_keys fk JOIN sys.tables t "
                    "ON fk.parent_object_id = t.object_id JOIN sys.schemas s "
                    "ON t.schema_id = s.schema_id WHERE s.name = 'trading') AS fk_count, "
                    "(SELECT COUNT(*) FROM sys.check_constraints cc JOIN sys.tables t "
                    "ON cc.parent_object_id = t.object_id JOIN sys.schemas s "
                    "ON t.schema_id = s.schema_id WHERE s.name = 'trading') AS check_count, "
                    "(SELECT COUNT(*) FROM sys.key_constraints kc JOIN sys.tables t "
                    "ON kc.parent_object_id = t.object_id JOIN sys.schemas s "
                    "ON t.schema_id = s.schema_id "
                    "WHERE s.name = 'trading' AND kc.type = 'UQ') AS unique_count"
                )
            )
            .mappings()
            .one()
        )
        type_counts = (
            connection.execute(
                text(
                    "SELECT "
                    "SUM(CASE WHEN ty.name = 'decimal' THEN 1 ELSE 0 END) AS decimal_count, "
                    "SUM(CASE WHEN ty.name = 'decimal' AND (c.precision <> 38 OR c.scale <> 18) "
                    "THEN 1 ELSE 0 END) AS wrong_decimal_count, "
                    "SUM(CASE WHEN ty.name = 'datetimeoffset' THEN 1 ELSE 0 END) "
                    "AS datetimeoffset_count, "
                    "SUM(CASE WHEN ty.name = 'datetimeoffset' AND c.scale <> 7 THEN 1 ELSE 0 END) "
                    "AS wrong_datetimeoffset_count, "
                    "SUM(CASE WHEN ty.name = 'nvarchar' AND c.max_length = -1 THEN 1 ELSE 0 END) "
                    "AS nvarchar_max_count, "
                    "SUM(CASE WHEN ty.name = 'uniqueidentifier' THEN 1 ELSE 0 END) AS uuid_count "
                    "FROM sys.columns c JOIN sys.tables t ON c.object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "JOIN sys.types ty ON c.user_type_id = ty.user_type_id "
                    "WHERE s.name = 'trading'"
                )
            )
            .mappings()
            .one()
        )
        default_counts = (
            connection.execute(
                text(
                    "SELECT COUNT(*) AS recorded_default_count, "
                    "SUM(CASE WHEN dc.definition NOT LIKE '%SYSUTCDATETIME%' "
                    "OR dc.definition NOT LIKE '%TODATETIMEOFFSET%' THEN 1 ELSE 0 END) "
                    "AS wrong_recorded_default_count "
                    "FROM sys.default_constraints dc JOIN sys.columns c "
                    "ON dc.parent_object_id = c.object_id "
                    "AND dc.parent_column_id = c.column_id "
                    "JOIN sys.tables t ON c.object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "WHERE s.name = 'trading' AND c.name = 'recorded_at'"
                )
            )
            .mappings()
            .one()
        )
        filtered_indexes = {
            str(row["name"]): str(row["filter_definition"])
            for row in connection.execute(
                text(
                    "SELECT i.name, i.filter_definition FROM sys.indexes i "
                    "JOIN sys.tables t ON i.object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "WHERE s.name = 'trading' AND i.has_filter = 1"
                )
            ).mappings()
        }

    assert table_count == 11
    assert pk_count == 11
    assert wrong_delete_actions == 0
    assert filtered_count == 3
    assert constraint_counts["fk_count"] == expected_fk_count
    assert constraint_counts["check_count"] == expected_check_count
    assert constraint_counts["unique_count"] == expected_unique_count
    assert type_counts["decimal_count"] == expected_decimal_count
    assert type_counts["wrong_decimal_count"] == 0
    assert type_counts["datetimeoffset_count"] == expected_datetime_count
    assert type_counts["wrong_datetimeoffset_count"] == 0
    assert type_counts["nvarchar_max_count"] == 3
    assert type_counts["uuid_count"] == expected_uuid_count
    assert default_counts["recorded_default_count"] == 11
    assert default_counts["wrong_recorded_default_count"] == 0
    assert set(filtered_indexes) == {
        "ix_paper_positions_open_unique",
        "ix_strategy_decisions_candidate_unique",
        "ix_paper_orders_broker_ref_unique",
    }
    assert "status" in filtered_indexes["ix_paper_positions_open_unique"]
    assert "candidate_id" in filtered_indexes["ix_strategy_decisions_candidate_unique"]
    assert "broker_order_ref" in filtered_indexes["ix_paper_orders_broker_ref_unique"]
