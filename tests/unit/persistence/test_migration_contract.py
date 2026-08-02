import ast
import hashlib
import re
from io import StringIO
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES, metadata
from migrations.ddl import (
    create_daily_feature_outcome_tables,
    create_daily_feature_scoring_tables,
    create_daily_market_bars_table,
    create_execution_tables,
    create_feature_snapshot_table,
    create_market_tables,
    create_multi_symbol_feature_pipeline_tables,
    create_portfolio_tables,
    create_probability_calibration_dataset_tables,
    create_recommendations_table,
    create_strategy_tables,
    create_trading_events,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_ROOT = PROJECT_ROOT / "migrations"


def _migration_text() -> str:
    paths = sorted(MIGRATIONS_ROOT.rglob("*.py"))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _migration_columns() -> dict[str, tuple[str, ...]]:
    discovered: dict[str, tuple[str, ...]] = {}
    for path in sorted((MIGRATIONS_ROOT / "ddl").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_table"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                continue
            table_name = node.args[0].value
            columns = tuple(
                argument.args[0].value
                for argument in node.args[1:]
                if isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Attribute)
                and argument.func.attr == "Column"
                and argument.args
                and isinstance(argument.args[0], ast.Constant)
            )
            discovered[table_name] = columns
    return discovered


def test_revision_chain_and_initial_table_creation_set_are_stable() -> None:
    version = MIGRATIONS_ROOT / "versions" / "0001_create_mssql_canonical_schema.py"
    snapshot_migration = (
        MIGRATIONS_ROOT / "versions" / "0002_add_position_decision_market_snapshot.py"
    )
    version_migration = MIGRATIONS_ROOT / "versions" / "0003_add_position_decision_version.py"
    feature_migration = MIGRATIONS_ROOT / "versions" / "0004_add_feature_snapshots.py"
    recommendation_migration = MIGRATIONS_ROOT / "versions" / "0005_add_recommendations.py"
    daily_bar_migration = MIGRATIONS_ROOT / "versions" / "0006_add_daily_market_bars.py"
    assert version.exists()
    assert snapshot_migration.exists()
    assert version_migration.exists()
    assert feature_migration.exists()
    assert recommendation_migration.exists()
    assert daily_bar_migration.exists()
    assert 'revision: str = "0001_mssql_schema"' in version.read_text(encoding="utf-8")
    snapshot_text = snapshot_migration.read_text(encoding="utf-8")
    version_text = version_migration.read_text(encoding="utf-8")
    feature_text = feature_migration.read_text(encoding="utf-8")
    recommendation_text = recommendation_migration.read_text(encoding="utf-8")
    daily_bar_text = daily_bar_migration.read_text(encoding="utf-8")
    assert 'revision: str = "0002_position_snapshot"' in snapshot_text
    assert 'down_revision: str | None = "0001_mssql_schema"' in snapshot_text
    assert 'revision: str = "0003_position_decision_version"' in version_text
    assert 'down_revision: str | None = "0002_position_snapshot"' in version_text
    assert 'revision: str = "0004_feature_snapshots"' in feature_text
    assert 'down_revision: str | None = "0003_position_decision_version"' in feature_text
    assert 'revision: str = "0005_recommendations"' in recommendation_text
    assert 'down_revision: str | None = "0004_feature_snapshots"' in recommendation_text
    assert 'revision: str = "0006_daily_market_bars"' in daily_bar_text
    assert 'down_revision: str | None = "0005_recommendations"' in daily_bar_text

    text = _migration_text()
    created = set(re.findall(r'op\.create_table\(\s*"([a-z_]+)"', text))
    assert created == {table.name for table in BUSINESS_TABLES}


def test_migration_contains_every_metadata_constraint_and_index_name() -> None:
    text = _migration_text()
    expected_names = {
        name
        for table in BUSINESS_TABLES
        for name in [
            *(constraint.name for constraint in table.constraints),
            *(index.name for index in table.indexes),
        ]
        if name is not None
    }

    missing = {
        name
        for name in expected_names
        if f'"{name}"' not in text
        and not (
            (
                name.startswith("ck_recommendations_")
                and f'"{name.removeprefix("ck_recommendations_")}"' in text
            )
            or (
                name.startswith("ck_daily_market_bars_")
                and f'"{name.removeprefix("ck_daily_market_bars_")}"' in text
            )
            or any(
                name.startswith(prefix) and f'"{name.removeprefix(prefix)}"' in text
                for prefix in (
                    "ck_universe_snapshots_",
                    "ck_daily_feature_pipeline_runs_",
                    "ck_daily_feature_pipeline_items_",
                    "ck_daily_feature_scoring_runs_",
                    "ck_daily_feature_scoring_items_",
                    "ck_daily_feature_outcomes_",
                    "ck_daily_feature_outcome_observation_runs_",
                    "ck_daily_feature_outcome_observation_run_items_",
                    "ck_daily_feature_outcome_labels_",
                    "ck_probability_calibration_datasets_",
                    "ck_probability_calibration_dataset_items_",
                )
            )
        )
    }
    assert missing == set()


def test_offline_migration_preserves_frozen_check_constraint_names() -> None:
    output = StringIO()
    context = MigrationContext.configure(
        dialect=mssql.dialect(),
        opts={"as_sql": True, "output_buffer": output, "target_metadata": metadata},
    )
    operations = Operations(context)

    create_market_tables(operations)
    create_daily_market_bars_table(operations)
    create_feature_snapshot_table(operations)
    create_recommendations_table(operations)
    create_portfolio_tables(operations, positions_only=True)
    create_strategy_tables(operations)
    create_execution_tables(operations)
    create_portfolio_tables(operations, positions_only=False)
    create_trading_events(operations)
    create_multi_symbol_feature_pipeline_tables(operations)
    create_daily_feature_scoring_tables(operations)
    create_daily_feature_outcome_tables(operations)
    create_probability_calibration_dataset_tables(operations)

    ddl = output.getvalue()
    expected_names = {
        constraint.name
        for table in BUSINESS_TABLES
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    additive_names = {
        "ck_strategy_decisions_candidate_without_snapshot",
        "ck_strategy_decisions_candidate_without_position_version",
        "ck_strategy_decisions_position_requires_snapshot",
        "ck_strategy_decisions_position_requires_version",
        "ck_strategy_decisions_position_version_positive",
    }
    expected_names -= additive_names
    assert all(name in ddl for name in expected_names)
    assert all(f"ck_{table.name}_ck_{table.name}_" not in ddl for table in BUSINESS_TABLES)
    additive_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            MIGRATIONS_ROOT / "versions" / "0002_add_position_decision_market_snapshot.py",
            MIGRATIONS_ROOT / "versions" / "0003_add_position_decision_version.py",
        )
    )
    assert all(name in additive_text for name in additive_names)


def test_initial_migration_columns_plus_additive_columns_match_metadata() -> None:
    expected = {
        table.name: tuple(column.name for column in table.columns) for table in BUSINESS_TABLES
    }
    expected["strategy_decisions"] = tuple(
        name
        for name in expected["strategy_decisions"]
        if name not in {"market_snapshot_id", "position_version"}
    )

    assert _migration_columns() == expected
    additive = (
        MIGRATIONS_ROOT / "versions" / "0002_add_position_decision_market_snapshot.py"
    ).read_text(encoding="utf-8")
    version_additive = (
        MIGRATIONS_ROOT / "versions" / "0003_add_position_decision_version.py"
    ).read_text(encoding="utf-8")
    assert 'sa.Column("market_snapshot_id", uuid_type(), nullable=True)' in additive
    assert 'sa.Column("position_version", sa.Integer(), nullable=True)' in version_additive


def test_migration_has_no_database_creation_batch_separator_or_seed_data() -> None:
    text = _migration_text()
    upper = text.upper()

    assert "CREATE DATABASE" not in upper
    assert "DROP DATABASE" not in upper
    assert re.search(r"(?m)^\s*GO\s*$", text, flags=re.IGNORECASE) is None
    assert re.search(r"(?m)^\s*USE\s+", text, flags=re.IGNORECASE) is None
    assert "INSERT INTO" not in upper
    assert "METADATA.CREATE_ALL" not in upper


def test_legacy_migrations_are_byte_for_byte_unchanged_from_exact_base() -> None:
    expected = {
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
    }

    for name, digest in expected.items():
        raw = (MIGRATIONS_ROOT / "versions" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest


def test_0004_upgrade_and_downgrade_touch_only_feature_snapshots() -> None:
    migration = MIGRATIONS_ROOT / "versions" / "0004_add_feature_snapshots.py"
    text = migration.read_text(encoding="utf-8")

    assert "create_feature_snapshot_table(op)" in text
    assert 'op.drop_table("feature_snapshots", schema="trading")' in text
    assert "alter_column" not in text
    assert "add_column" not in text
    assert "drop_column" not in text
    assert "execute(" not in text


def test_0005_upgrade_and_downgrade_touch_only_recommendations() -> None:
    migration = MIGRATIONS_ROOT / "versions" / "0005_add_recommendations.py"
    text = migration.read_text(encoding="utf-8")

    assert "create_recommendations_table(op)" in text
    assert 'op.drop_table("recommendations", schema="trading")' in text
    assert "alter_column" not in text
    assert "add_column" not in text
    assert "drop_column" not in text
    assert "execute(" not in text


def test_0006_upgrade_and_downgrade_touch_only_daily_market_bars() -> None:
    migration = MIGRATIONS_ROOT / "versions" / "0006_add_daily_market_bars.py"
    text = migration.read_text(encoding="utf-8")

    assert "create_daily_market_bars_table(op)" in text
    assert 'op.drop_table("daily_market_bars", schema="trading")' in text
    assert "alter_column" not in text
    assert "add_column" not in text
    assert "drop_column" not in text
    assert "execute(" not in text


def test_alembic_environment_has_no_hardcoded_connection_url() -> None:
    env_text = (MIGRATIONS_ROOT / "env.py").read_text(encoding="utf-8")
    ini_text = (PROJECT_ROOT / "alembic.ini").read_text(encoding="utf-8")

    assert "AUTO_TRADING_V2_DATABASE_URL" not in ini_text
    assert "sqlalchemy.url =\n" in ini_text
    assert "DATABASE_URL_ENV" in env_text
    assert "target_metadata=target_metadata" in env_text
