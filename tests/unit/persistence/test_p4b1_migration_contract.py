from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects import mssql

from migrations.ddl import create_daily_feature_outcome_tables

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
    "0008_add_daily_feature_scoring.py": (
        "58b1557f62f78f65b9d6722ac4e824d12bc33b8670fcac7235524a117b90dd25"
    ),
}


def test_0009_revision_chain_and_legacy_migrations_are_exact() -> None:
    text = (VERSIONS / "0009_add_daily_feature_outcomes.py").read_text(encoding="utf-8")
    assert 'revision: str = "0009_daily_feature_outcomes"' in text
    assert 'down_revision: str | None = "0008_daily_feature_scoring"' in text
    for name, expected in LEGACY_HASHES.items():
        assert hashlib.sha256((VERSIONS / name).read_bytes()).hexdigest() == expected


def test_0009_upgrade_and_downgrade_touch_only_three_p4b1_tables() -> None:
    text = (VERSIONS / "0009_add_daily_feature_outcomes.py").read_text(encoding="utf-8")
    assert "create_daily_feature_outcome_tables(op)" in text
    assert re.findall(r'op\.drop_table\("([a-z_]+)", schema="trading"\)', text) == [
        "daily_feature_outcome_observation_run_items",
        "daily_feature_outcome_observation_runs",
        "daily_feature_outcomes",
    ]
    for forbidden in ("add_column", "drop_column", "execute(", "alter_column"):
        assert forbidden not in text


def test_0009_offline_ddl_contains_frozen_shapes_and_decimal_types() -> None:
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect=mssql.dialect(),
        opts={"as_sql": True, "output_buffer": output},
    )
    create_daily_feature_outcome_tables(Operations(context))
    ddl = output.getvalue()

    assert ddl.count("CREATE TABLE trading.daily_feature_outcome") == 3
    assert "DECIMAL(38, 18)" in ddl
    assert "ck_daily_feature_outcomes_provenance_json" in ddl
    assert "ck_daily_feature_outcome_observation_runs_status_shape" in ddl
    assert "ck_daily_feature_outcome_observation_run_items_outcome_shape" in ddl
    assert "completion_grace_seconds INTEGER NOT NULL" in ddl
    assert ddl.count("ON DELETE NO ACTION") == 9
