"""Pure deterministic strategy-decision engine."""

from auto_trading_v2.domain.strategy_decisions.errors import StrategySignalMismatchError
from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyAction,
    StrategyDecisionResult,
    StrategyDefinition,
    StrategySignal,
)
from auto_trading_v2.domain.strategy_decisions.reason_codes import (
    extract_blocking_reason_codes,
)


class DeterministicStrategyDecisionEngine:
    """Map one validated canonical filter signal to one strategy action."""

    def decide(
        self,
        signal: StrategySignal,
        definition: StrategyDefinition,
    ) -> StrategyDecisionResult:
        if (
            signal.filter_set_id != definition.source_filter_set_id
            or signal.evaluation_version != definition.source_evaluation_version
        ):
            raise StrategySignalMismatchError("strategy signal identity does not match policy")

        blocking = extract_blocking_reason_codes(
            signal.details,
            require_non_empty=not signal.passed,
        )
        reasons: tuple[str, ...]
        if definition.observation_only:
            action = StrategyAction.OBSERVE
            reasons = ("OBSERVATION_ONLY",)
        elif signal.passed:
            action = StrategyAction.ENTER_LONG
            reasons = ("FILTER_SET_PASSED", "ENTRY_ALLOWED")
        else:
            action = StrategyAction.SKIP
            reasons = ("FILTER_SET_FAILED", *blocking, "ENTRY_BLOCKED")

        return StrategyDecisionResult(
            strategy_id=definition.strategy_id,
            strategy_name=definition.name,
            strategy_version=definition.strategy_version,
            source_filter_set_id=definition.source_filter_set_id,
            source_evaluation_version=definition.source_evaluation_version,
            action=action,
            reason_codes=reasons,
        )
