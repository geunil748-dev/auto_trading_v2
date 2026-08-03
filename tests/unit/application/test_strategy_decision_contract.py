from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction


def decision() -> NewCandidateStrategyDecision:
    return NewCandidateStrategyDecision(
        decision_id=DecisionID(uuid4()),
        decision_key=(
            "candidate:11111111-1111-4111-8111-111111111111|"
            "strategy:22222222-2222-4222-8222-222222222222|version:v1"
        ),
        candidate_id=CandidateID(uuid4()),
        filter_evaluation_id=FilterEvaluationID(uuid4()),
        strategy_id=StrategyID(uuid4()),
        strategy_version="v1",
        action=StrategyAction.ENTER_LONG,
        reason_codes=("FILTER_SET_PASSED", "ENTRY_ALLOWED"),
        decided_at=datetime(2026, 7, 14, 15, tzinfo=timezone(timedelta(hours=9))),
    )


def test_contract_is_frozen_typed_and_normalizes_utc() -> None:
    value = decision()

    assert isinstance(value.decision_id, DecisionID)
    assert isinstance(value.candidate_id, CandidateID)
    assert isinstance(value.filter_evaluation_id, FilterEvaluationID)
    assert isinstance(value.strategy_id, StrategyID)
    assert value.action is StrategyAction.ENTER_LONG
    assert value.decided_at == datetime(2026, 7, 14, 6, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        value.action = StrategyAction.SKIP  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("decision_key", ""),
        ("decision_key", "has space"),
        ("decision_key", "x" * 161),
        ("strategy_version", ""),
        ("strategy_version", " v1"),
        ("reason_codes", ()),
        ("reason_codes", ("lowercase",)),
        ("reason_codes", ("A", "A")),
        ("reason_codes", ["A"]),
    ],
)
def test_contract_rejects_invalid_codes_and_keys(field: str, invalid: object) -> None:
    with pytest.raises(ValidationError):
        replace(decision(), **{field: invalid})


def test_contract_rejects_naive_datetime_and_wrong_identifier_types() -> None:
    with pytest.raises(ValidationError):
        replace(decision(), decided_at=datetime(2026, 7, 14))
    with pytest.raises(ValidationError):
        replace(decision(), decision_id=uuid4())


def test_candidate_contract_does_not_expand_to_exit_actions() -> None:
    with pytest.raises(ValidationError):
        replace(decision(), action=StrategyAction.EXIT_LONG)


def test_stored_contract_adds_only_recorded_at() -> None:
    new = decision()
    stored = StoredCandidateStrategyDecision(
        **{field.name: getattr(new, field.name) for field in fields(new)},
        recorded_at=datetime(2026, 7, 14, 7, tzinfo=UTC),
    )

    assert stored.recorded_at == datetime(2026, 7, 14, 7, tzinfo=UTC)
    assert "position_id" not in {field.name for field in fields(stored)}
