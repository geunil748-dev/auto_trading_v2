import hashlib
import io
import re
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import CheckConstraint, Numeric
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_outcome_labels,
    probability_calibration_dataset_items,
    probability_calibration_datasets,
)
from migrations.ddl import create_probability_calibration_dataset_tables

ROOT = Path(__file__).resolve().parents[3]
VERSIONS = ROOT / "migrations" / "versions"
BASE_0009_SHA256 = "226148b09d2062be709a9412ec0a88424417de00d9a080c260d2fbbfc77fe22e"


def test_0010_revision_is_additive_and_downgrades_in_dependency_order() -> None:
    path = VERSIONS / "0010_add_outcome_labels_calibration_dataset.py"
    text = path.read_text(encoding="utf-8")

    assert 'revision: str = "0010_outcome_labels_calibration_dataset"' in text
    assert 'down_revision: str | None = "0009_daily_feature_outcomes"' in text
    assert "create_probability_calibration_dataset_tables(op)" in text
    assert re.findall(r'op\.drop_table\("([a-z_]+)", schema="trading"\)', text) == [
        "probability_calibration_dataset_items",
        "probability_calibration_datasets",
        "daily_feature_outcome_labels",
    ]
    for forbidden in ("add_column", "drop_column", "alter_column", "execute("):
        assert forbidden not in text


def test_0009_is_unchanged_and_0010_offline_ddl_creates_exactly_three_tables() -> None:
    assert (
        hashlib.sha256((VERSIONS / "0009_add_daily_feature_outcomes.py").read_bytes()).hexdigest()
        == BASE_0009_SHA256
    )
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect=mssql.dialect(), opts={"as_sql": True, "output_buffer": output}
    )
    create_probability_calibration_dataset_tables(Operations(context))
    ddl = output.getvalue()

    assert ddl.count("CREATE TABLE trading.") == 3
    assert ddl.index("daily_feature_outcome_labels") < ddl.index("probability_calibration_datasets")
    assert ddl.index("probability_calibration_datasets") < ddl.index(
        "probability_calibration_dataset_items"
    )
    assert "DECIMAL(9, 6)" in ddl
    assert "ON DELETE NO ACTION" in ddl


def test_three_metadata_tables_have_frozen_constraints_indexes_and_decimal_shape() -> None:
    tables = (
        daily_feature_outcome_labels,
        probability_calibration_datasets,
        probability_calibration_dataset_items,
    )
    assert {table.name for table in tables} == {
        "daily_feature_outcome_labels",
        "probability_calibration_datasets",
        "probability_calibration_dataset_items",
    }
    assert all(table.schema == "trading" for table in tables)
    assert all(
        constraint.name
        for table in tables
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert all(index.name for table in tables for index in table.indexes)
    score = probability_calibration_dataset_items.c.overall_relative_score.type
    assert isinstance(score, Numeric)
    assert (score.precision, score.scale, score.asdecimal) == (9, 6, True)
    assert all(
        foreign_key.ondelete == "NO ACTION"
        for table in tables
        for foreign_key in table.foreign_key_constraints
    )
