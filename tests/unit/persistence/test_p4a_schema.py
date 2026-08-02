from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, UniqueConstraint

from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
)

SCORES = {
    "momentum_score",
    "trend_score",
    "breakout_score",
    "price_action_score",
    "stability_score",
    "volume_score",
    "overall_relative_score",
}


def _columns(table: object, kind: type) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, kind)
    }


def _checks(table: object) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _indexes(table: object) -> set[tuple[str, ...]]:
    return {tuple(column.name for column in index.columns) for index in table.indexes}


def test_scoring_run_has_exact_identity_fks_uniques_and_indexes() -> None:
    assert _columns(daily_feature_scoring_runs, ForeignKeyConstraint) == {
        ("source_daily_feature_pipeline_run_id",)
    }
    assert all(fk.ondelete == "NO ACTION" for fk in daily_feature_scoring_runs.foreign_keys)
    assert _columns(daily_feature_scoring_runs, UniqueConstraint) == {
        ("scoring_run_key",),
        (
            "source_daily_feature_pipeline_run_id",
            "scoring_policy_code",
            "scoring_policy_version",
            "ranking_policy_code",
            "ranking_policy_version",
        ),
    }
    assert _indexes(daily_feature_scoring_runs) == {
        ("source_daily_feature_pipeline_run_id",),
        ("status", "generated_at"),
        ("scoring_policy_code", "scoring_policy_version", "generated_at"),
    }
    sql = _checks(daily_feature_scoring_runs)
    assert "total_count = scored_ready_count + scored_degraded_count + unscorable_count" in sql
    assert "NO_SCORABLE_ITEMS" in sql
    assert "DATALENGTH(scoring_run_key) = 93" in sql


def test_scoring_item_has_fixed_decimal_shape_fks_uniques_and_indexes() -> None:
    assert _columns(daily_feature_scoring_items, ForeignKeyConstraint) == {
        ("daily_feature_scoring_run_id",),
        ("source_daily_feature_pipeline_item_id",),
        ("feature_snapshot_id",),
    }
    assert all(fk.ondelete == "NO ACTION" for fk in daily_feature_scoring_items.foreign_keys)
    assert _columns(daily_feature_scoring_items, UniqueConstraint) == {
        ("daily_feature_scoring_run_id", "ordinal"),
        ("daily_feature_scoring_run_id", "source_daily_feature_pipeline_item_id"),
        ("daily_feature_scoring_run_id", "symbol"),
    }
    for name in SCORES:
        score_type = daily_feature_scoring_items.c[name].type
        assert isinstance(score_type, Numeric)
        assert (score_type.precision, score_type.scale, score_type.asdecimal) == (9, 6, True)
    assert _indexes(daily_feature_scoring_items) == {
        ("daily_feature_scoring_run_id", "rank"),
        ("symbol", "generated_at"),
        ("outcome", "generated_at"),
        ("feature_snapshot_id",),
        ("overall_relative_score",),
    }
    sql = _checks(daily_feature_scoring_items)
    assert "SCORED_READY" in sql and "volume_score IS NOT NULL" in sql
    assert "SCORED_DEGRADED" in sql and "volume_score IS NULL" in sql
    assert "safe_reason_code IS NOT NULL" in sql
    assert "ordinal BETWEEN 1 AND 100" in sql


def test_scoring_public_schema_has_no_prediction_fields() -> None:
    forbidden = {"probability", "confidence", "expected_value", "win_rate", "success_rate"}
    columns = {column.name for column in daily_feature_scoring_runs.columns}
    columns |= {column.name for column in daily_feature_scoring_items.columns}
    assert not any(token in column for token in forbidden for column in columns)
