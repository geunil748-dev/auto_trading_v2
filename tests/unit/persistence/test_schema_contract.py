from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    feature_snapshots,
    filter_evaluations,
    paper_orders,
    paper_positions,
    strategy_decisions,
    trade_intents,
)
from auto_trading_v2.adapters.persistence.types import currency_check_sql, symbol_check_sql
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives.symbol import Symbol


def _constraint_columns(table: object, constraint_type: type) -> set[tuple[str, ...]]:
    constraints = table.constraints
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if isinstance(constraint, constraint_type)
    }


def test_canonical_tables_do_not_duplicate_upstream_business_values() -> None:
    assert "strategy_id" not in candidates.c
    assert "symbol" not in candidates.c
    assert "symbol" not in paper_orders.c
    assert "quantity" not in paper_orders.c
    assert "side" not in paper_orders.c
    assert "order_type" not in paper_orders.c


def test_required_semantic_unique_constraints_are_present() -> None:
    assert ("run_id", "market_snapshot_id", "candidate_source") in _constraint_columns(
        candidates, UniqueConstraint
    )
    assert ("candidate_id", "filter_set_id", "evaluation_version") in _constraint_columns(
        filter_evaluations, UniqueConstraint
    )
    assert ("decision_id",) in _constraint_columns(trade_intents, UniqueConstraint)
    assert ("trade_intent_id",) in _constraint_columns(paper_orders, UniqueConstraint)
    assert ("client_order_id",) in _constraint_columns(paper_orders, UniqueConstraint)
    assert ("snapshot_key",) in _constraint_columns(feature_snapshots, UniqueConstraint)
    assert (
        "symbol",
        "feature_set_code",
        "feature_set_version",
        "horizon_trading_days",
        "as_of",
    ) in _constraint_columns(feature_snapshots, UniqueConstraint)


def test_filtered_unique_indexes_are_explicit_mssql_contracts() -> None:
    expected = {
        "ix_paper_positions_open_unique": "status = 'OPEN'",
        "ix_strategy_decisions_candidate_unique": "candidate_id IS NOT NULL",
        "ix_strategy_decisions_position_snapshot_unique": "position_id IS NOT NULL",
        "ix_paper_orders_broker_ref_unique": "broker_order_ref IS NOT NULL",
    }
    indexes = {
        index.name: str(index.dialect_options["mssql"]["where"])
        for table in (paper_positions, strategy_decisions, paper_orders)
        for index in table.indexes
        if index.unique
    }

    assert indexes == expected


def test_position_decision_snapshot_fk_and_indexes_are_canonical() -> None:
    foreign_keys = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in strategy_decisions.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in strategy_decisions.indexes
    }

    assert foreign_keys["fk_strategy_decisions_market_snapshot_id_market_snapshots"] == (
        "market_snapshot_id",
    )
    assert foreign_keys["fk_strategy_decisions_position_version_position_events"] == (
        "position_id",
        "position_version",
    )
    assert indexes["ix_strategy_decisions_market_snapshot"] == ("market_snapshot_id",)
    assert indexes["ix_strategy_decisions_position_decided"] == ("position_id", "decided_at")
    assert indexes["ix_strategy_decisions_position_version"] == (
        "position_id",
        "position_version",
    )
    assert "ix_strategy_decisions_position" not in indexes


def test_symbol_check_matches_domain_allowed_character_policy() -> None:
    expression = symbol_check_sql()
    assert "[A-Z0-9]" in expression
    assert "[^A-Z0-9.-]" in expression
    assert "DATALENGTH(symbol) BETWEEN 1 AND 32" in expression
    for valid in ("A", "BRK.B", "ABC-1", "1234"):
        assert Symbol(valid).serialize() == valid
    for invalid in ("", "A/B", "a b", "A" * 33):
        try:
            Symbol(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"invalid symbol accepted: {invalid}")


def test_currency_check_is_binary_uppercase_ascii_policy() -> None:
    expression = currency_check_sql()
    assert "DATALENGTH(currency) = 3" in expression
    assert "[^A-Z]" in expression
    assert "Latin1_General_100_BIN2" in expression


def test_json_shape_checks_and_state_checks_are_present() -> None:
    check_sql = {
        table.name: " ".join(
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
        for table in (
            filter_evaluations,
            feature_snapshots,
            strategy_decisions,
            paper_positions,
            paper_orders,
        )
    }

    assert "ISJSON(details) = 1" in check_sql["filter_evaluations"]
    assert "ISJSON(reason_codes) = 1" in check_sql["strategy_decisions"]
    assert "ISJSON(feature_values) = 1" in check_sql["feature_snapshots"]
    assert "ISJSON(provenance) = 1" in check_sql["feature_snapshots"]
    assert "horizon_trading_days BETWEEN 1 AND 5" in check_sql["feature_snapshots"]
    assert "generated_at >= as_of" in check_sql["feature_snapshots"]
    assert "latest_input_available_at <= as_of" in check_sql["feature_snapshots"]
    assert "candidate_id IS NULL OR market_snapshot_id IS NULL" in check_sql["strategy_decisions"]
    assert (
        "position_id IS NULL OR market_snapshot_id IS NOT NULL" in check_sql["strategy_decisions"]
    )
    assert "candidate_id IS NULL OR position_version IS NULL" in check_sql["strategy_decisions"]
    assert "position_id IS NULL OR position_version IS NOT NULL" in check_sql["strategy_decisions"]
    assert "position_version IS NULL OR position_version > 0" in check_sql["strategy_decisions"]
    assert "status = 'OPEN'" in check_sql["paper_positions"]
    assert "PARTIALLY_FILLED" in check_sql["paper_orders"]


def test_feature_snapshot_indexes_are_exact_and_content_digest_is_not_unique() -> None:
    indexes = {
        index.name: (
            tuple(column.name for column in index.columns),
            index.unique,
        )
        for index in feature_snapshots.indexes
    }

    assert indexes == {
        "ix_feature_snapshots_content_digest": (("content_digest",), False),
        "ix_feature_snapshots_quality_as_of": (("quality_status", "as_of"), False),
        "ix_feature_snapshots_set_as_of": (
            ("feature_set_code", "feature_set_version", "as_of"),
            False,
        ),
        "ix_feature_snapshots_symbol_as_of": (("symbol", "as_of"), False),
    }
