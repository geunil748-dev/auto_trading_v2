"""Immutable application boundary contracts."""

from auto_trading_v2.application.contracts.persistence import (
    JSONValue,
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
    StoredCandidate,
    StoredFilterEvaluation,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)

__all__ = [
    "JSONValue",
    "NewCandidate",
    "NewCandidateStrategyDecision",
    "NewFilterEvaluation",
    "NewMarketSnapshot",
    "StoredCandidate",
    "StoredCandidateStrategyDecision",
    "StoredFilterEvaluation",
    "StoredMarketSnapshot",
]
