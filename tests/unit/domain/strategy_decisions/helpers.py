from decimal import Decimal

from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyDefinition,
    StrategyJSONValue,
    StrategySignal,
)


def signal(
    definition: StrategyDefinition,
    *,
    passed: bool = True,
    score: str = "100",
    blocking: list[str] | None = None,
    details: dict[str, StrategyJSONValue] | None = None,
) -> StrategySignal:
    return StrategySignal(
        filter_set_id=definition.source_filter_set_id,
        evaluation_version=definition.source_evaluation_version,
        passed=passed,
        score=Decimal(score),
        details=(
            details
            if details is not None
            else {"blocking_reason_codes": [] if blocking is None else blocking}
        ),
    )
