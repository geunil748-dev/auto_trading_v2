"""Typed ID generation boundaries for canonical records."""

from typing import Protocol

from auto_trading_v2.domain.primitives import DecisionID, FilterEvaluationID


class FilterEvaluationIDFactory(Protocol):
    """Create only per-evaluation IDs; filter-set IDs come from the catalog."""

    def new(self) -> FilterEvaluationID: ...


class DecisionIDFactory(Protocol):
    """Create only per-decision IDs; strategy IDs come from the catalog."""

    def new(self) -> DecisionID: ...
