"""Pure deterministic filter scoring and overall pass policy."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from auto_trading_v2.domain.filtering.checks import evaluate_checks
from auto_trading_v2.domain.filtering.models import (
    FilterEvaluationResult,
    FilterInput,
    FilterMode,
    FilterOutcome,
    FilterSetDefinition,
)


class DeterministicFilterEngine:
    """Evaluate one immutable input against one immutable definition."""

    def evaluate(
        self,
        filter_input: FilterInput,
        definition: FilterSetDefinition,
    ) -> FilterEvaluationResult:
        checks = evaluate_checks(filter_input, definition)
        with localcontext() as context:
            context.prec = 38
            context.rounding = ROUND_HALF_EVEN
            score = sum(
                (check.weight for check in checks if check.outcome is FilterOutcome.PASS),
                Decimal("0"),
            )

        hard_failed = any(check.hard and check.outcome is FilterOutcome.FAIL for check in checks)
        hard_not_evaluable = any(
            check.hard and check.outcome is FilterOutcome.NOT_EVALUABLE for check in checks
        )
        score_below = score < definition.minimum_score
        if definition.mode is FilterMode.OBSERVATION:
            passed = True
            blocking: tuple[str, ...] = ()
        else:
            passed = not hard_failed and not hard_not_evaluable and not score_below
            blocking = tuple(
                code
                for condition, code in (
                    (hard_failed, "HARD_CHECK_FAILED"),
                    (hard_not_evaluable, "HARD_CHECK_NOT_EVALUABLE"),
                    (score_below, "SCORE_BELOW_MINIMUM"),
                )
                if condition
            )

        return FilterEvaluationResult(
            filter_set_id=definition.filter_set_id,
            filter_set_name=definition.name,
            evaluation_version=definition.evaluation_version,
            mode=definition.mode,
            passed=passed,
            score=score,
            checks=checks,
            blocking_reason_codes=blocking,
        )
