import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.application.errors import (
    CheckConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    PersistenceUnavailableError,
)


@pytest.mark.parametrize("code", [2601, 2627])
def test_duplicate_translation_exposes_only_safe_context(code: int) -> None:
    raw = Exception(
        "23000",
        f"private server login password SQL params ({code}) "
        "uq_market_snapshots_source_symbol_observed",
    )
    exc = IntegrityError("private SELECT", {"payload": "private"}, raw)

    translated = translate_persistence_error(exc, entity="market_snapshot", operation="insert")

    assert isinstance(translated, DuplicateRecordError)
    assert translated.constraint == "uq_market_snapshots_source_symbol_observed"
    rendered = str(translated)
    for secret in ("server", "login", "password", "SELECT", "params", "payload"):
        assert secret not in rendered


def test_foreign_key_and_check_translation() -> None:
    foreign_key = IntegrityError(
        None,
        None,
        Exception(
            "23000",
            "The INSERT statement conflicted with the FOREIGN KEY constraint "
            "fk_candidates_market_snapshot_id_market_snapshots. (547)",
        ),
    )
    check = IntegrityError(
        None,
        None,
        Exception(
            "23000",
            "The INSERT statement conflicted with the CHECK constraint "
            "ck_candidates_rank_positive. (547)",
        ),
    )

    assert isinstance(
        translate_persistence_error(foreign_key, entity="candidate", operation="insert"),
        ForeignKeyViolationError,
    )
    assert isinstance(
        translate_persistence_error(check, entity="candidate", operation="insert"),
        CheckConstraintViolationError,
    )


def test_strategy_constraints_translate_to_safe_categories() -> None:
    duplicate = IntegrityError(
        None,
        None,
        Exception("23000", "ix_strategy_decisions_candidate_unique (2601)"),
    )
    foreign_key = IntegrityError(
        None,
        None,
        Exception(
            "23000",
            "FOREIGN KEY constraint "
            "fk_strategy_decisions_filter_evaluation_id_filter_evaluations (547)",
        ),
    )
    check = IntegrityError(
        None,
        None,
        Exception("23000", "CHECK constraint ck_strategy_decisions_action (547)"),
    )

    assert isinstance(
        translate_persistence_error(duplicate, entity="strategy_decision", operation="insert"),
        DuplicateRecordError,
    )
    assert isinstance(
        translate_persistence_error(foreign_key, entity="strategy_decision", operation="insert"),
        ForeignKeyViolationError,
    )
    assert isinstance(
        translate_persistence_error(check, entity="strategy_decision", operation="insert"),
        CheckConstraintViolationError,
    )


def test_connection_sqlstate_maps_to_unavailable_without_raw_error() -> None:
    exc = OperationalError("private SQL", None, Exception("08001", "private host"))

    translated = translate_persistence_error(exc, entity="record", operation="select")

    assert isinstance(translated, PersistenceUnavailableError)
    assert "private" not in str(translated)
