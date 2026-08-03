from decimal import ROUND_DOWN, ROUND_UP, getcontext, localcontext

from auto_trading_v2.domain.primitives import CandidateID
from auto_trading_v2.domain.strategy_decisions.catalog import STRICT_ENTRY
from auto_trading_v2.domain.strategy_decisions.decision_keys import (
    candidate_strategy_decision_key,
)
from auto_trading_v2.domain.strategy_decisions.engine import (
    DeterministicStrategyDecisionEngine,
)

from .helpers import signal


def test_result_and_key_ignore_global_decimal_context_and_randomness() -> None:
    value = signal(STRICT_ENTRY, passed=True, score="59.999999999999999999")
    candidate_id = CandidateID.parse("55555555-5555-4555-8555-555555555555")
    engine = DeterministicStrategyDecisionEngine()
    original = getcontext().copy()
    try:
        with localcontext() as context:
            context.prec = 6
            context.rounding = ROUND_DOWN
            first = engine.decide(value, STRICT_ENTRY)
        with localcontext() as context:
            context.prec = 38
            context.rounding = ROUND_UP
            second = engine.decide(value, STRICT_ENTRY)
    finally:
        getcontext().prec = original.prec
        getcontext().rounding = original.rounding

    assert first == second
    assert first.action == second.action
    assert first.reason_codes == second.reason_codes
    assert candidate_strategy_decision_key(
        candidate_id, first.strategy_id, first.strategy_version
    ) == candidate_strategy_decision_key(candidate_id, second.strategy_id, second.strategy_version)
