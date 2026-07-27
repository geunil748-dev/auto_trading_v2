"""Canonical table registry in dependency creation order."""

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.tables.events import trading_events
from auto_trading_v2.adapters.persistence.tables.execution import paper_fills, paper_orders
from auto_trading_v2.adapters.persistence.tables.features import feature_snapshots
from auto_trading_v2.adapters.persistence.tables.market import (
    candidates,
    filter_evaluations,
    market_snapshots,
)
from auto_trading_v2.adapters.persistence.tables.portfolio import (
    equity_snapshots,
    paper_positions,
    position_events,
)
from auto_trading_v2.adapters.persistence.tables.recommendations import recommendations
from auto_trading_v2.adapters.persistence.tables.strategy import (
    strategy_decisions,
    trade_intents,
)

BUSINESS_TABLES = (
    market_snapshots,
    feature_snapshots,
    recommendations,
    candidates,
    filter_evaluations,
    paper_positions,
    strategy_decisions,
    trade_intents,
    paper_orders,
    paper_fills,
    position_events,
    equity_snapshots,
    trading_events,
)

__all__ = [
    "BUSINESS_TABLES",
    "candidates",
    "equity_snapshots",
    "filter_evaluations",
    "feature_snapshots",
    "market_snapshots",
    "metadata",
    "paper_fills",
    "paper_orders",
    "paper_positions",
    "position_events",
    "recommendations",
    "strategy_decisions",
    "trade_intents",
    "trading_events",
]
