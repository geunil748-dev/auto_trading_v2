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

__all__ = [
    "JSONValue",
    "NewCandidate",
    "NewFilterEvaluation",
    "NewMarketSnapshot",
    "StoredCandidate",
    "StoredFilterEvaluation",
    "StoredMarketSnapshot",
]
