from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects import mssql

from migrations.ddl import create_daily_feature_scoring_tables

ROOT = Path(__file__).resolve().parents[3]
VERSIONS = ROOT / "migrations" / "versions"
LEGACY_HASHES = {
    "0001_create_mssql_canonical_schema.py": (
        "15f489b9052128ff085f3ef7519ba809199bde6d1a34886f41f8f72198ac9a0b"
    ),
    "0002_add_position_decision_market_snapshot.py": (
        "7c13c288b088f5aa78f99880153bc5edf2aa2e0a94cab7f41a882d19c9be276a"
    ),
    "0003_add_position_decision_version.py": (
        "b291fd408601f7a4216af0fa00510f6e1668314095b2e450c58a08655674ff9f"
    ),
    "0004_add_feature_snapshots.py": (
        "ac9da953ebe4e94b6b94baa11a5a66812bd1b8a490e8dc2ba5cf2767a8379562"
    ),
    "0005_add_recommendations.py": (
        "aee79c16aa958b499eec679b26ba8e760999c2ee427412c7d6ce7f2c70e49a26"
    ),
    "0006_add_daily_market_bars.py": (
        "856d3201b5a973adba0d9508a640e2c414f96de124218b8483dad5e79093e7da"
    ),
    "0007_add_multi_symbol_feature_pipeline.py": (
        "986299667c3b28763e3854ecd2afdccb7cac96c927a5e62745f5bf7440a4e496"
    ),
}


def test_0008_revision_chain_and_legacy_migrations_are_exact() -> None:
    text = (VERSIONS / "0008_add_daily_feature_scoring.py").read_text(encoding="utf-8")
    assert 'revision: str = "0008_daily_feature_scoring"' in text
    assert 'down_revision: str | None = "0007_multi_symbol_feature_pipeline"' in text
    for name, expected in LEGACY_HASHES.items():
        assert hashlib.sha256((VERSIONS / name).read_bytes()).hexdigest() == expected


def test_0008_upgrade_and_downgrade_touch_only_two_p4a_tables() -> None:
    text = (VERSIONS / "0008_add_daily_feature_scoring.py").read_text(encoding="utf-8")
    assert "create_daily_feature_scoring_tables(op)" in text
    assert re.findall(r'op\.drop_table\("([a-z_]+)", schema="trading"\)', text) == [
        "daily_feature_scoring_items",
        "daily_feature_scoring_runs",
    ]
    assert "add_column" not in text
    assert "drop_column" not in text
    assert "execute(" not in text


def test_0008_offline_ddl_contains_frozen_shapes_and_decimal_types() -> None:
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect=mssql.dialect(),
        opts={"as_sql": True, "output_buffer": output},
    )
    create_daily_feature_scoring_tables(Operations(context))
    ddl = output.getvalue()
    assert "CREATE TABLE trading.daily_feature_scoring_runs" in ddl
    assert "CREATE TABLE trading.daily_feature_scoring_items" in ddl
    assert "DECIMAL(9, 6)" in ddl
    assert "ck_daily_feature_scoring_items_outcome_shape" in ddl
    assert "ON DELETE NO ACTION" in ddl
