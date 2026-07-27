"""Validated domain value objects."""

from auto_trading_v2.domain.primitives.identifiers import (
    CandidateID,
    ClientOrderID,
    DecisionID,
    EquitySnapshotID,
    EventID,
    FeatureSnapshotID,
    FillID,
    FilterEvaluationID,
    FilterSetID,
    IdentifierFactory,
    MarketSnapshotID,
    NotificationID,
    OrderID,
    PositionEventID,
    PositionID,
    RunID,
    StrategyID,
    TradeIntentID,
)
from auto_trading_v2.domain.primitives.money import Currency, Money
from auto_trading_v2.domain.primitives.numbers import Price, Quantity, Rate
from auto_trading_v2.domain.primitives.symbol import Symbol
from auto_trading_v2.domain.primitives.time import SessionDate, UtcTimestamp

__all__ = [
    "CandidateID",
    "ClientOrderID",
    "Currency",
    "DecisionID",
    "EquitySnapshotID",
    "EventID",
    "FeatureSnapshotID",
    "FillID",
    "FilterEvaluationID",
    "FilterSetID",
    "IdentifierFactory",
    "MarketSnapshotID",
    "Money",
    "NotificationID",
    "OrderID",
    "PositionID",
    "PositionEventID",
    "Price",
    "Quantity",
    "Rate",
    "RunID",
    "SessionDate",
    "StrategyID",
    "Symbol",
    "TradeIntentID",
    "UtcTimestamp",
]
