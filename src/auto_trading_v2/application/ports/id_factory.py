"""Typed ID generation boundary for filter evaluations."""

from typing import Protocol

from auto_trading_v2.domain.primitives import FilterEvaluationID


class FilterEvaluationIDFactory(Protocol):
    """Create only per-evaluation IDs; filter-set IDs come from the catalog."""

    def new(self) -> FilterEvaluationID: ...
