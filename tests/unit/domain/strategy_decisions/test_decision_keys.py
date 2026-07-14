from uuid import UUID

import pytest

from auto_trading_v2.domain.primitives import CandidateID, StrategyID
from auto_trading_v2.domain.strategy_decisions.decision_keys import (
    candidate_strategy_decision_key,
)
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError

CANDIDATE = CandidateID(UUID("11111111-1111-4111-8111-111111111111"))
STRATEGY = StrategyID(UUID("22222222-2222-4222-8222-222222222222"))


def test_decision_key_has_exact_semantic_format() -> None:
    key = candidate_strategy_decision_key(CANDIDATE, STRATEGY, "v1")

    assert key == (
        "candidate:11111111-1111-4111-8111-111111111111|"
        "strategy:22222222-2222-4222-8222-222222222222|version:v1"
    )
    assert len(key) <= 160
    assert not any(character.isspace() for character in key)


def test_key_is_stable_and_each_semantic_component_changes_it() -> None:
    same = candidate_strategy_decision_key(CANDIDATE, STRATEGY, "v1")

    assert candidate_strategy_decision_key(CANDIDATE, STRATEGY, "v1") == same
    assert (
        candidate_strategy_decision_key(
            CandidateID(UUID("33333333-3333-4333-8333-333333333333")), STRATEGY, "v1"
        )
        != same
    )
    assert (
        candidate_strategy_decision_key(
            CANDIDATE, StrategyID(UUID("44444444-4444-4444-8444-444444444444")), "v1"
        )
        != same
    )
    assert candidate_strategy_decision_key(CANDIDATE, STRATEGY, "v2") != same


def test_key_rejects_a_version_that_would_exceed_storage() -> None:
    with pytest.raises(StrategyValidationError):
        candidate_strategy_decision_key(CANDIDATE, STRATEGY, "V" * 64)
