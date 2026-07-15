"""Typed ID generation boundaries for canonical records."""

from typing import Protocol

from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    DecisionID,
    FillID,
    FilterEvaluationID,
    OrderID,
    TradeIntentID,
)


class FilterEvaluationIDFactory(Protocol):
    """Create only per-evaluation IDs; filter-set IDs come from the catalog."""

    def new(self) -> FilterEvaluationID: ...


class DecisionIDFactory(Protocol):
    """Create only per-decision IDs; strategy IDs come from the catalog."""

    def new(self) -> DecisionID: ...


class TradeIntentIDFactory(Protocol):
    """Create canonical trade-intent IDs only for eligible decisions."""

    def new(self) -> TradeIntentID: ...


class ClientOrderIDFactory(Protocol):
    """Create the deterministic broker request identity for a TradeIntent."""

    def for_trade_intent(self, trade_intent_id: TradeIntentID) -> ClientOrderID: ...


class OrderIDFactory(Protocol):
    """Create canonical PaperOrder identifiers."""

    def new(self) -> OrderID: ...


class FillIDFactory(Protocol):
    """Create canonical PaperFill identifiers."""

    def new(self) -> FillID: ...
