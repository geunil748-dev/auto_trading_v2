from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from auto_trading_v2.domain.primitives import FilterSetID
from auto_trading_v2.domain.strategy_decisions.catalog import (
    BALANCED_ENTRY,
    OBSERVATION_ONLY,
    SCORE_ONLY_ENTRY,
    STRICT_ENTRY,
)
from auto_trading_v2.domain.strategy_decisions.engine import (
    DeterministicStrategyDecisionEngine,
)
from auto_trading_v2.domain.strategy_decisions.errors import StrategySignalMismatchError
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction

from .helpers import signal

ENTRY_STRATEGIES = (STRICT_ENTRY, BALANCED_ENTRY, SCORE_ONLY_ENTRY)


@pytest.mark.parametrize("definition", ENTRY_STRATEGIES, ids=lambda item: item.name.value)
def test_entry_strategy_uses_persisted_passed_true(definition: object) -> None:
    typed = next(item for item in ENTRY_STRATEGIES if item is definition)
    result = DeterministicStrategyDecisionEngine().decide(
        signal(typed, passed=True, score="0"), typed
    )

    assert result.action is StrategyAction.ENTER_LONG
    assert result.reason_codes == ("FILTER_SET_PASSED", "ENTRY_ALLOWED")


@pytest.mark.parametrize("definition", ENTRY_STRATEGIES, ids=lambda item: item.name.value)
def test_entry_strategy_uses_persisted_passed_false(definition: object) -> None:
    typed = next(item for item in ENTRY_STRATEGIES if item is definition)
    result = DeterministicStrategyDecisionEngine().decide(
        signal(
            typed,
            passed=False,
            score="100",
            blocking=[
                "HARD_CHECK_FAILED",
                "HARD_CHECK_FAILED",
                "SCORE_BELOW_MINIMUM",
            ],
        ),
        typed,
    )

    assert result.action is StrategyAction.SKIP
    assert result.reason_codes == (
        "FILTER_SET_FAILED",
        "HARD_CHECK_FAILED",
        "SCORE_BELOW_MINIMUM",
        "ENTRY_BLOCKED",
    )


@pytest.mark.parametrize("passed", [True, False])
def test_observation_always_observes(passed: bool) -> None:
    result = DeterministicStrategyDecisionEngine().decide(
        signal(
            OBSERVATION_ONLY,
            passed=passed,
            blocking=None if passed else ["HARD_CHECK_FAILED"],
        ),
        OBSERVATION_ONLY,
    )

    assert result.action is StrategyAction.OBSERVE
    assert result.reason_codes == ("OBSERVATION_ONLY",)
    assert result.action is not StrategyAction.ENTER_LONG


def test_signal_filter_identity_and_version_must_match() -> None:
    engine = DeterministicStrategyDecisionEngine()
    wrong_id = signal(STRICT_ENTRY)
    object.__setattr__(wrong_id, "filter_set_id", FilterSetID(uuid4()))
    wrong_version = signal(STRICT_ENTRY)
    object.__setattr__(wrong_version, "evaluation_version", "v2")

    with pytest.raises(StrategySignalMismatchError):
        engine.decide(wrong_id, STRICT_ENTRY)
    with pytest.raises(StrategySignalMismatchError):
        engine.decide(wrong_version, STRICT_ENTRY)


def test_result_is_immutable() -> None:
    result = DeterministicStrategyDecisionEngine().decide(signal(STRICT_ENTRY), STRICT_ENTRY)

    with pytest.raises(FrozenInstanceError):
        result.action = StrategyAction.SKIP  # type: ignore[misc]
