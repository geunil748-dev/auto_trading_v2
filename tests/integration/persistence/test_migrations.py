import pytest
from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint, inspect, text
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    daily_market_bars,
    feature_snapshots,
    recommendations,
)
from tests.integration.persistence.catalog_helpers import (
    revision as _revision,
)
from tests.integration.persistence.catalog_helpers import (
    table_catalog_signature as _table_catalog_signature,
)

pytestmark = pytest.mark.integration

P3_TABLE_NAMES = {
    "universe_snapshots",
    "daily_feature_pipeline_runs",
    "daily_feature_pipeline_items",
    "daily_feature_scoring_runs",
    "daily_feature_scoring_items",
    "daily_feature_outcomes",
    "daily_feature_outcome_observation_runs",
    "daily_feature_outcome_observation_run_items",
    "daily_feature_outcome_labels",
    "probability_calibration_datasets",
    "probability_calibration_dataset_items",
}


def _without_p3(*names: str) -> set[str]:
    return {table.name for table in BUSINESS_TABLES} - P3_TABLE_NAMES - set(names)


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
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
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
    prior_tables = _without_p3(
        daily_market_bars.name,
        feature_snapshots.name,
        recommendations.name,
    )
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    signature_before = _table_catalog_signature(mssql_database, prior_tables)
    mssql_database.run_downgrade("0003_position_decision_version")
    assert _revision(mssql_database) == "0003_position_decision_version"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_upgrade("head")
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == expected_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_check()


def test_recommendation_revision_round_trip_preserves_prior_schema(
    mssql_database: object,
) -> None:
    expected_tables = {table.name for table in BUSINESS_TABLES}
    prior_tables = _without_p3(daily_market_bars.name, recommendations.name)
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
    signature_before = _table_catalog_signature(mssql_database, prior_tables)
    mssql_database.run_downgrade("0004_feature_snapshots")
    assert _revision(mssql_database) == "0004_feature_snapshots"
    assert set(inspect(mssql_database.engine).get_table_names(schema="trading")) == prior_tables
    assert _table_catalog_signature(mssql_database, prior_tables) == signature_before
    mssql_database.run_upgrade("head")
    assert _revision(mssql_database) == "0010_outcome_labels_calibration_dataset"
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
    fixed_scale_decimal = (
        "(t.name = 'daily_feature_scoring_items' AND c.name IN ('momentum_score',"
        "'trend_score','breakout_score','price_action_score','stability_score',"
        "'volume_score','overall_relative_score')) OR "
        "(t.name = 'probability_calibration_dataset_items' "
        "AND c.name = 'overall_relative_score')"
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
                    "SUM(CASE WHEN ty.name = 'decimal' AND ("
                    f"c.precision <> CASE WHEN ({fixed_scale_decimal}) THEN 9 ELSE 38 END OR "
                    f"c.scale <> CASE WHEN ({fixed_scale_decimal}) THEN 6 ELSE 18 END"
                    ") THEN 1 ELSE 0 END) AS wrong_decimal_count, "
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
