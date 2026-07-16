"""Stable immutable built-in strategy and position-exit policy catalog."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.domain.filtering.catalog import (
    BALANCED,
    OBSERVATION,
    SCORE_ONLY,
    STRICT,
)
from auto_trading_v2.domain.primitives import Currency, Rate, StrategyID
from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyDefinition,
    StrategyName,
)
from auto_trading_v2.domain.strategy_decisions.position_exit import PositionExitPolicy

STRATEGY_VERSION = "v1"

STRICT_ENTRY = StrategyDefinition(
    strategy_id=StrategyID(UUID("10c3fbc4-7db0-5980-9f85-8fbfc944a26c")),
    name=StrategyName.STRICT_ENTRY,
    strategy_version=STRATEGY_VERSION,
    source_filter_set_id=STRICT.filter_set_id,
    source_filter_set_name=STRICT.name,
    source_evaluation_version=STRICT.evaluation_version,
    observation_only=False,
)

BALANCED_ENTRY = StrategyDefinition(
    strategy_id=StrategyID(UUID("4bb90f07-6f29-5a8f-ada7-7d5952eb0c9a")),
    name=StrategyName.BALANCED_ENTRY,
    strategy_version=STRATEGY_VERSION,
    source_filter_set_id=BALANCED.filter_set_id,
    source_filter_set_name=BALANCED.name,
    source_evaluation_version=BALANCED.evaluation_version,
    observation_only=False,
)

SCORE_ONLY_ENTRY = StrategyDefinition(
    strategy_id=StrategyID(UUID("78b1169a-80d4-5894-8f45-b3c85cf5b2b6")),
    name=StrategyName.SCORE_ONLY_ENTRY,
    strategy_version=STRATEGY_VERSION,
    source_filter_set_id=SCORE_ONLY.filter_set_id,
    source_filter_set_name=SCORE_ONLY.name,
    source_evaluation_version=SCORE_ONLY.evaluation_version,
    observation_only=False,
)

OBSERVATION_ONLY = StrategyDefinition(
    strategy_id=StrategyID(UUID("86132628-8c1d-5eec-abcc-02ca3c3c39a5")),
    name=StrategyName.OBSERVATION_ONLY,
    strategy_version=STRATEGY_VERSION,
    source_filter_set_id=OBSERVATION.filter_set_id,
    source_filter_set_name=OBSERVATION.name,
    source_evaluation_version=OBSERVATION.evaluation_version,
    observation_only=True,
)

BUILT_IN_STRATEGIES = (
    STRICT_ENTRY,
    BALANCED_ENTRY,
    SCORE_ONLY_ENTRY,
    OBSERVATION_ONLY,
)

FIXED_POSITION_EXIT = PositionExitPolicy(
    name="FIXED_POSITION_EXIT",
    version="v1",
    currency=Currency("USD"),
    stop_loss_rate=Rate(Decimal("-0.05")),
    take_profit_rate=Rate(Decimal("0.10")),
    maximum_holding_duration=timedelta(hours=6),
    snapshot_maximum_age=timedelta(minutes=5),
    future_clock_skew_tolerance=timedelta(seconds=30),
)

POSITION_EXIT_STRATEGIES = (
    STRICT_ENTRY,
    BALANCED_ENTRY,
    SCORE_ONLY_ENTRY,
)


def position_exit_policy_for(
    strategy_id: StrategyID,
    strategy_version: str,
) -> PositionExitPolicy | None:
    """Return the pinned exit policy for an eligible entry strategy version."""

    if not isinstance(strategy_id, StrategyID) or not isinstance(strategy_version, str):
        return None
    supported = any(
        definition.strategy_id == strategy_id and definition.strategy_version == strategy_version
        for definition in POSITION_EXIT_STRATEGIES
    )
    return FIXED_POSITION_EXIT if supported else None
