import pytest
from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint, inspect, text
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    feature_snapshots,
    recommendations,
)

pytestmark = pytest.mark.integration


def _revision(mssql_database: object) -> str:
    with mssql_database.engine.connect() as connection:
        return str(
            connection.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar_one()
        )


def _normalized(value: object) -> object:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _normalized(item)) for key, item in value.items()))
    if isinstance(value, list | tuple):
        return tuple(_normalized(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _table_catalog_signature(mssql_database: object, table_names: set[str]) -> object:
    inspector = inspect(mssql_database.engine)
    with mssql_database.engine.connect() as connection:
        constraints = tuple(
            sorted(
                tuple(str(value) for value in row)
                for row in connection.execute(
                    text(
                        "SELECT t.name, o.type, o.name, COALESCE(cc.definition, '') "
                        "FROM sys.objects o JOIN sys.tables t "
                        "ON o.parent_object_id = t.object_id JOIN sys.schemas s "
                        "ON t.schema_id = s.schema_id LEFT JOIN sys.check_constraints cc "
                        "ON o.object_id = cc.object_id WHERE s.name = 'trading' "
                        "AND o.type IN ('PK', 'UQ', 'C')"
                    )
                ).tuples()
                if str(row[0]) in table_names
            )
        )
    reflected = tuple(
        (
            table_name,
            _normalized(inspector.get_columns(table_name, schema="trading")),
            _normalized(inspector.get_pk_constraint(table_name, schema="trading")),
            _normalized(inspector.get_foreign_keys(table_name, schema="trading")),
            _normalized(inspector.get_indexes(table_name, schema="trading")),
        )
        for table_name in sorted(table_names)
    )
    return reflected, constraints


def _filtered_index_names() -> set[str]:
    names = {
        index.name
        for table in BUSINESS_TABLES
        for index in table.indexes
        if index.dialect_options["mssql"].get("where") is not None
    }
    assert None not in names
    return {str(name) for name in names}


def test_migration_revision_catalog_and_drift(mssql_database: object) -> None:
    expected = {table.name for table in BUSINESS_TABLES}
    inspector = inspect(mssql_database.engine)
    assert set(inspector.get_table_names(schema="trading")) == expected
    assert _revision(mssql_database) == "0005_recommendations"
    mssql_database.run_check()


def test_downgrade_and_reupgrade_only_temporary_database(mssql_database: object) -> None:
    assert mssql_database.name.startswith("auto_trading_v2_test_")

    mssql_database.run_downgrade("base")
    inspector = inspect(mssql_database.engine)
    assert inspector.get_table_names(schema="trading") == []

    mssql_database.run_upgrade("head")
    assert len(inspect(mssql_database.engine).get_table_names(schema="trading")) == len(
        BUSINESS_TABLES
    )
    mssql_database.run_check()


def test_feature_snapshot_revision_round_trip_preserves_prior_schema(
    mssql_database: object,
) -> None:
    expected_tables = {table.name for table in BUSINESS_TABLES}
    prior_tables = expected_tables - {feature_snapshots.name, recommendations.name}
    assert _revision(mssql_database) == "0005_recommendations"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    signature_before = _table_catalog_signature(mssql_database, prior_tables)

    mssql_database.run_downgrade("0003_position_decision_version")

    assert _revision(mssql_database) == "0003_position_decision_version"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before

    mssql_database.run_upgrade("head")

    assert _revision(mssql_database) == "0005_recommendations"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_check()


def test_recommendation_revision_round_trip_preserves_prior_schema(
    mssql_database: object,
) -> None:
    expected_tables = {table.name for table in BUSINESS_TABLES}
    prior_tables = expected_tables - {recommendations.name}
    assert _revision(mssql_database) == "0005_recommendations"
    signature_before = _table_catalog_signature(mssql_database, prior_tables)

    mssql_database.run_downgrade("0004_feature_snapshots")

    assert _revision(mssql_database) == "0004_feature_snapshots"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before

    mssql_database.run_upgrade("head")

    assert _revision(mssql_database) == "0005_recommendations"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_check()


def test_sql_server_catalog_contract(mssql_database: object) -> None:
    expected_table_count = len(BUSINESS_TABLES)
    expected_pk_count = sum(len(table.primary_key.columns) > 0 for table in BUSINESS_TABLES)
    expected_recorded_default_count = sum("recorded_at" in table.c for table in BUSINESS_TABLES)
    expected_nvarchar_max_count = sum(
        isinstance(column.type, mssql.NVARCHAR) and column.type.length is None
        for table in BUSINESS_TABLES
        for column in table.columns
    )
    expected_filtered_indexes = _filtered_index_names()
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

    assert table_count == expected_table_count
    assert pk_count == expected_pk_count
    assert wrong_delete_actions == 0
    assert filtered_count == len(expected_filtered_indexes)
    assert constraint_counts["fk_count"] == expected_fk_count
    assert constraint_counts["check_count"] == expected_check_count
    assert constraint_counts["unique_count"] == expected_unique_count
    assert type_counts["decimal_count"] == expected_decimal_count
    assert type_counts["wrong_decimal_count"] == 0
    assert type_counts["datetimeoffset_count"] == expected_datetime_count
    assert type_counts["wrong_datetimeoffset_count"] == 0
    assert type_counts["nvarchar_max_count"] == expected_nvarchar_max_count
    assert type_counts["uuid_count"] == expected_uuid_count
    assert default_counts["recorded_default_count"] == expected_recorded_default_count
    assert default_counts["wrong_recorded_default_count"] == 0
    assert expected_filtered_indexes == {
        "ix_paper_positions_open_unique",
        "ix_strategy_decisions_candidate_unique",
        "ix_strategy_decisions_position_snapshot_unique",
        "ix_paper_orders_broker_ref_unique",
    }
    assert set(filtered_indexes) == expected_filtered_indexes
    assert "status" in filtered_indexes["ix_paper_positions_open_unique"]
    assert "candidate_id" in filtered_indexes["ix_strategy_decisions_candidate_unique"]
    assert "position_id" in filtered_indexes["ix_strategy_decisions_position_snapshot_unique"]
    assert "broker_order_ref" in filtered_indexes["ix_paper_orders_broker_ref_unique"]
