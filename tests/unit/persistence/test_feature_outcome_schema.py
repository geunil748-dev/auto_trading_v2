from sqlalchemy import Integer, Numeric
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_outcome_observation_run_items,
    daily_feature_outcome_observation_runs,
    daily_feature_outcomes,
)


def _checks(table: object) -> set[str]:
    return {
        constraint.name for constraint in table.constraints if constraint.name.startswith("ck_")
    }


def test_outcome_table_has_exact_decimal_json_fk_unique_and_index_contract() -> None:
    table = daily_feature_outcomes
    decimal_names = {
        "reference_close",
        "terminal_close",
        "forward_close_return",
        "maximum_favorable_excursion_rate",
        "maximum_adverse_excursion_rate",
    }

    assert {column.name for column in table.columns if isinstance(column.type, Numeric)} == (
        decimal_names
    )
    assert all(
        (table.c[name].type.precision, table.c[name].type.scale) == (38, 18)
        for name in decimal_names
    )
    assert isinstance(table.c.future_bar_provenance.type, mssql.NVARCHAR)
    assert table.c.future_bar_provenance.type.length is None
    assert len(table.foreign_key_constraints) == 5
    assert len(table.indexes) == 6
    assert "ck_daily_feature_outcomes_provenance_json" in _checks(table)
    assert "ck_daily_feature_outcomes_rate_order" in _checks(table)
    assert not any(
        constraint.name and "content_digest" in constraint.name
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )


def test_observation_run_and_item_tables_freeze_count_and_shape_contracts() -> None:
    runs = daily_feature_outcome_observation_runs
    items = daily_feature_outcome_observation_run_items

    assert isinstance(runs.c.completion_grace_seconds.type, Integer)
    assert "ck_daily_feature_outcome_observation_runs_status_shape" in _checks(runs)
    assert "ck_daily_feature_outcome_observation_runs_count_sum" in _checks(runs)
    assert len(runs.indexes) == 3
    assert len(items.foreign_key_constraints) == 3
    assert "ck_daily_feature_outcome_observation_run_items_outcome_shape" in _checks(items)
    assert len(items.indexes) == 4
