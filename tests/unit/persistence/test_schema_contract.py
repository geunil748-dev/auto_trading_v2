from sqlalchemy import CheckConstraint, UniqueConstraint

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
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


def test_filtered_unique_indexes_are_explicit_mssql_contracts() -> None:
    expected = {
        "ix_paper_positions_open_unique": "status = 'OPEN'",
        "ix_strategy_decisions_candidate_unique": "candidate_id IS NOT NULL",
        "ix_paper_orders_broker_ref_unique": "broker_order_ref IS NOT NULL",
    }
    indexes = {
        index.name: str(index.dialect_options["mssql"]["where"])
        for table in (paper_positions, strategy_decisions, paper_orders)
        for index in table.indexes
        if index.unique
    }

    assert indexes == expected


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
        for table in (filter_evaluations, strategy_decisions, paper_positions, paper_orders)
    }

    assert "ISJSON(details) = 1" in check_sql["filter_evaluations"]
    assert "ISJSON(reason_codes) = 1" in check_sql["strategy_decisions"]
    assert "status = 'OPEN'" in check_sql["paper_positions"]
    assert "PARTIALLY_FILLED" in check_sql["paper_orders"]
