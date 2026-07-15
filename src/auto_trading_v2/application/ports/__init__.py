"""Application ports implemented by external adapters."""

from auto_trading_v2.application.ports.id_factory import (
    ClientOrderIDFactory,
    DecisionIDFactory,
    FilterEvaluationIDFactory,
    OrderIDFactory,
    TradeIntentIDFactory,
)
from auto_trading_v2.application.ports.paper_broker import PaperBroker, PaperBrokerError
from auto_trading_v2.application.ports.paper_orders import PaperOrderRepository
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
    "ClientOrderIDFactory",
    "DecisionIDFactory",
    "FilterEvaluationIDFactory",
    "FilterEvaluationRepository",
    "MarketSnapshotRepository",
    "OrderIDFactory",
    "PaperBroker",
    "PaperBrokerError",
    "PaperOrderRepository",
    "StrategyDecisionRepository",
    "TradeIntentIDFactory",
    "TradeIntentRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
