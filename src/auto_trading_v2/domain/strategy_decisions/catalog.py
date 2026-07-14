"""Stable immutable built-in strategy catalog."""

from uuid import UUID

from auto_trading_v2.domain.filtering.catalog import (
    BALANCED,
    OBSERVATION,
    SCORE_ONLY,
    STRICT,
)
from auto_trading_v2.domain.primitives import StrategyID
from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyDefinition,
    StrategyName,
)

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
