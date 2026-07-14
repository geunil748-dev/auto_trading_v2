"""Application ports implemented by external adapters."""

from auto_trading_v2.application.ports.id_factory import (
    DecisionIDFactory,
    FilterEvaluationIDFactory,
    TradeIntentIDFactory,
)
from auto_trading_v2.application.ports.repositories import (
    CandidateRepository,
    FilterEvaluationRepository,
    MarketSnapshotRepository,
)
from auto_trading_v2.application.ports.strategy_decisions import StrategyDecisionRepository
from auto_trading_v2.application.ports.trade_intents import TradeIntentRepository
from auto_trading_v2.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "CandidateRepository",
    "DecisionIDFactory",
    "FilterEvaluationIDFactory",
    "FilterEvaluationRepository",
    "MarketSnapshotRepository",
    "StrategyDecisionRepository",
    "TradeIntentIDFactory",
    "TradeIntentRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
