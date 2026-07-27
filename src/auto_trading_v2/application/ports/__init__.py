"""Application ports implemented by external adapters."""

from auto_trading_v2.application.ports.feature_snapshots import FeatureSnapshotRepository
from auto_trading_v2.application.ports.id_factory import (
    ClientOrderIDFactory,
    DecisionIDFactory,
    FeatureSnapshotIDFactory,
    FillIDFactory,
    FilterEvaluationIDFactory,
    OrderIDFactory,
    PositionEventIDFactory,
    PositionIDFactory,
    RecommendationIDFactory,
    TradeIntentIDFactory,
)
from auto_trading_v2.application.ports.paper_broker import PaperBroker, PaperBrokerError
from auto_trading_v2.application.ports.paper_fills import PaperFillRepository
from auto_trading_v2.application.ports.paper_orders import PaperOrderRepository
from auto_trading_v2.application.ports.position_projection import (
    PaperPositionRepository,
    PositionEventRepository,
)
from auto_trading_v2.application.ports.recommendations import RecommendationRepository
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
    "FeatureSnapshotIDFactory",
    "FeatureSnapshotRepository",
    "FilterEvaluationIDFactory",
    "FilterEvaluationRepository",
    "FillIDFactory",
    "MarketSnapshotRepository",
    "OrderIDFactory",
    "PaperPositionRepository",
    "PaperBroker",
    "PaperBrokerError",
    "PaperFillRepository",
    "PaperOrderRepository",
    "PositionEventIDFactory",
    "PositionEventRepository",
    "PositionIDFactory",
    "RecommendationIDFactory",
    "RecommendationRepository",
    "StrategyDecisionRepository",
    "TradeIntentIDFactory",
    "TradeIntentRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
