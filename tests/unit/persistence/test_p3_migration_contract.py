from __future__ import annotations

import io
import re
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects import mssql

from migrations.ddl import create_multi_symbol_feature_pipeline_tables
from migrations.version_table import VERSION_NUM_LENGTH, V2MssqlImpl

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_ROOT = PROJECT_ROOT / "migrations"


def test_0007_revision_chain_is_explicit() -> None:
    migration = MIGRATIONS_ROOT / "versions" / "0007_add_multi_symbol_feature_pipeline.py"
    text = migration.read_text(encoding="utf-8")

    assert 'revision: str = "0007_multi_symbol_feature_pipeline"' in text
    assert 'down_revision: str | None = "0006_daily_market_bars"' in text


def test_mssql_alembic_version_table_accepts_frozen_revision() -> None:
    implementation = V2MssqlImpl(mssql.dialect(), None, True, True, io.StringIO(), {})
    table = implementation.version_table_impl(
        version_table="alembic_version",
        version_table_schema="dbo",
        version_table_pk=True,
    )

    assert table.c.version_num.type.length == VERSION_NUM_LENGTH
    assert len("0007_multi_symbol_feature_pipeline") <= VERSION_NUM_LENGTH


def test_0007_upgrade_and_downgrade_touch_only_p3_tables() -> None:
    migration = MIGRATIONS_ROOT / "versions" / "0007_add_multi_symbol_feature_pipeline.py"
    text = migration.read_text(encoding="utf-8")

    assert "create_multi_symbol_feature_pipeline_tables(op)" in text
    dropped = re.findall(r'op\.drop_table\("([a-z_]+)", schema="trading"\)', text)
    assert dropped == [
        "daily_feature_pipeline_items",
        "daily_feature_pipeline_runs",
        "universe_snapshots",
    ]
    assert "alter_column" not in text
    assert "add_column" not in text
    assert "drop_column" not in text
    assert "execute(" not in text


def test_0007_offline_ddl_uses_frozen_constraint_names() -> None:
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect=mssql.dialect(),
        opts={"as_sql": True, "output_buffer": output},
    )
    create_multi_symbol_feature_pipeline_tables(Operations(context))

    ddl = output.getvalue()
    assert "ck_universe_snapshots_member_count" in ddl
    assert "ck_daily_feature_pipeline_runs_status" in ddl
    assert "ck_daily_feature_pipeline_items_outcome" in ddl
