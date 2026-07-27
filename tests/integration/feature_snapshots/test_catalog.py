from datetime import timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.feature_snapshot_mapping import (
    serialize_feature_values,
    serialize_provenance,
    serialize_quality_reasons,
)
from auto_trading_v2.adapters.persistence.tables import feature_snapshots
from tests.integration.feature_snapshots.helpers import new_snapshot
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration

EXPECTED_COLUMNS = (
    "feature_snapshot_id",
    "snapshot_key",
    "content_digest",
    "symbol",
    "feature_set_code",
    "feature_set_version",
    "horizon_trading_days",
    "as_of",
    "generated_at",
    "latest_input_available_at",
    "quality_status",
    "quality_reason_codes",
    "feature_values",
    "provenance",
    "recorded_at",
)
EXPECTED_CHECKS = {
    "ck_feature_snapshots_symbol",
    "ck_feature_snapshots_feature_set_code_nonempty",
    "ck_feature_snapshots_feature_set_version_nonempty",
    "ck_feature_snapshots_horizon",
    "ck_feature_snapshots_generated_after_cutoff",
    "ck_feature_snapshots_latest_input_before_cutoff",
    "ck_feature_snapshots_quality_status",
    "ck_feature_snapshots_quality_reason_codes_json_array",
    "ck_feature_snapshots_feature_values_json_object",
    "ck_feature_snapshots_provenance_json_array",
    "ck_feature_snapshots_feature_values_nonempty",
    "ck_feature_snapshots_provenance_nonempty",
    "ck_feature_snapshots_quality_reasons",
    "ck_feature_snapshots_snapshot_key_format",
    "ck_feature_snapshots_content_digest_format",
}
EXPECTED_INDEXES = {
    "pk_feature_snapshots",
    "uq_feature_snapshots_snapshot_key",
    "uq_feature_snapshots_semantic_identity",
    "ix_feature_snapshots_symbol_as_of",
    "ix_feature_snapshots_set_as_of",
    "ix_feature_snapshots_quality_as_of",
    "ix_feature_snapshots_content_digest",
}


def _valid_row(case: int) -> dict[str, object]:
    snapshot = new_snapshot(case)
    source = snapshot.snapshot_input
    return {
        "feature_snapshot_id": snapshot.feature_snapshot_id.value,
        "snapshot_key": snapshot.snapshot_key,
        "content_digest": snapshot.content_digest,
        "symbol": source.symbol.value,
        "feature_set_code": source.feature_set_code,
        "feature_set_version": source.feature_set_version,
        "horizon_trading_days": source.horizon.value,
        "as_of": source.as_of,
        "generated_at": snapshot.generated_at,
        "latest_input_available_at": source.latest_input_available_at,
        "quality_status": source.quality_status.value,
        "quality_reason_codes": serialize_quality_reasons(source),
        "feature_values": serialize_feature_values(source),
        "provenance": serialize_provenance(source),
    }


def test_live_feature_snapshot_catalog_is_exact(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    object_id = "OBJECT_ID('trading.feature_snapshots')"
    with mssql_database.engine.connect() as connection:
        columns = list(
            connection.execute(
                text(
                    "SELECT c.name, ty.name AS type_name, c.max_length, c.scale, "
                    "c.is_nullable, c.collation_name FROM sys.columns c JOIN sys.types ty "
                    "ON c.user_type_id = ty.user_type_id "
                    f"WHERE c.object_id = {object_id} ORDER BY c.column_id"
                )
            ).mappings()
        )
        checks = {
            str(value)
            for value in connection.execute(
                text(f"SELECT name FROM sys.check_constraints WHERE parent_object_id={object_id}")
            ).scalars()
        }
        keys = {
            (str(row["name"]), str(row["type"]))
            for row in connection.execute(
                text(
                    f"SELECT name, type FROM sys.key_constraints WHERE parent_object_id={object_id}"
                )
            ).mappings()
        }
        indexes = {
            str(value)
            for value in connection.execute(
                text(
                    f"SELECT name FROM sys.indexes WHERE object_id={object_id} "
                    "AND name IS NOT NULL AND is_hypothetical=0"
                )
            ).scalars()
        }
        foreign_key_count = connection.execute(
            text(f"SELECT COUNT(*) FROM sys.foreign_keys WHERE parent_object_id={object_id}")
        ).scalar_one()
        recorded_default = connection.execute(
            text(
                "SELECT dc.definition FROM sys.default_constraints dc JOIN sys.columns c "
                "ON dc.parent_object_id=c.object_id AND dc.parent_column_id=c.column_id "
                f"WHERE c.object_id={object_id} AND c.name='recorded_at'"
            )
        ).scalar_one()

    by_name = {str(row["name"]): row for row in columns}
    assert tuple(by_name) == EXPECTED_COLUMNS
    assert by_name["feature_snapshot_id"]["type_name"] == "uniqueidentifier"
    assert by_name["horizon_trading_days"]["type_name"] == "smallint"
    assert all(
        by_name[name]["type_name"] == "datetimeoffset"
        for name in ("as_of", "generated_at", "latest_input_available_at", "recorded_at")
    )
    assert all(
        by_name[name]["scale"] == 7
        for name in ("as_of", "generated_at", "latest_input_available_at", "recorded_at")
    )
    assert all(
        by_name[name]["max_length"] == -1
        for name in ("quality_reason_codes", "feature_values", "provenance")
    )
    assert by_name["snapshot_key"]["max_length"] == 84
    assert by_name["content_digest"]["max_length"] == 64
    assert by_name["snapshot_key"]["collation_name"] == "Latin1_General_100_BIN2"
    assert by_name["content_digest"]["collation_name"] == "Latin1_General_100_BIN2"
    assert all(row["is_nullable"] is False for row in columns)
    assert checks == EXPECTED_CHECKS
    assert keys == {
        ("pk_feature_snapshots", "PK"),
        ("uq_feature_snapshots_snapshot_key", "UQ"),
        ("uq_feature_snapshots_semantic_identity", "UQ"),
    }
    assert indexes == EXPECTED_INDEXES
    assert foreign_key_count == 0
    normalized_default = str(recorded_default).upper()
    assert "SYSUTCDATETIME" in normalized_default
    assert "TODATETIMEOFFSET" in normalized_default


@pytest.mark.parametrize(
    "invalid_case",
    [
        "horizon_zero",
        "horizon_six",
        "generated_before_as_of",
        "latest_after_as_of",
        "invalid_feature_json",
        "empty_feature_values",
        "empty_provenance",
        "ready_with_reasons",
        "degraded_without_reasons",
        "bad_snapshot_key",
        "bad_content_digest",
    ],
)
def test_live_constraints_reject_invalid_rows_without_residue(
    mssql_database: TemporaryMssqlDatabase,
    invalid_case: str,
) -> None:
    row = _valid_row(400)
    if invalid_case == "horizon_zero":
        row["horizon_trading_days"] = 0
    elif invalid_case == "horizon_six":
        row["horizon_trading_days"] = 6
    elif invalid_case == "generated_before_as_of":
        row["generated_at"] = row["as_of"] - timedelta(seconds=1)
    elif invalid_case == "latest_after_as_of":
        row["latest_input_available_at"] = row["as_of"] + timedelta(seconds=1)
    elif invalid_case == "invalid_feature_json":
        row["feature_values"] = "not-json"
    elif invalid_case == "empty_feature_values":
        row["feature_values"] = "{}"
    elif invalid_case == "empty_provenance":
        row["provenance"] = "[]"
    elif invalid_case == "ready_with_reasons":
        row["quality_reason_codes"] = '["MISSING_INPUT"]'
    elif invalid_case == "degraded_without_reasons":
        row["quality_status"] = "DEGRADED"
    elif invalid_case == "bad_snapshot_key":
        row["snapshot_key"] = "invalid"
    else:
        row["content_digest"] = "g" * 64

    identifier = row["feature_snapshot_id"]
    with mssql_database.engine.connect() as connection:
        transaction = connection.begin()
        with pytest.raises(IntegrityError):
            connection.execute(feature_snapshots.insert().values(**row))
        transaction.rollback()
    with mssql_database.engine.connect() as connection:
        count = connection.execute(
            select(func.count())
            .select_from(feature_snapshots)
            .where(feature_snapshots.c.feature_snapshot_id == identifier)
        ).scalar_one()
    assert count == 0
