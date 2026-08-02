"""Application ports implemented by external adapters."""

from auto_trading_v2.application.ports.batch_budget import (
    DailyMarketDataBatchBudgetPort,
    DailyMarketDataProviderRole,
)
from auto_trading_v2.application.ports.daily_market_bars import DailyMarketBarRepository
from auto_trading_v2.application.ports.daily_market_data import (
    CompletedDailyMarketBarObservation,
    DailyMarketDataProvider,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.application.ports.feature_pipeline import (
    DailyFeaturePipelineRunRepository,
)
from auto_trading_v2.application.ports.feature_scoring import (
    DailyFeatureScoringRunRepository,
)
from auto_trading_v2.application.ports.feature_snapshots import FeatureSnapshotRepository
from auto_trading_v2.application.ports.id_factory import (
    ClientOrderIDFactory,
    DailyFeaturePipelineItemIDFactory,
    DailyFeaturePipelineRunIDFactory,
    DailyFeatureScoringItemIDFactory,
    DailyFeatureScoringRunIDFactory,
    DailyMarketBarIDFactory,
    DecisionIDFactory,
    FeatureSnapshotIDFactory,
    FillIDFactory,
    FilterEvaluationIDFactory,
    OrderIDFactory,
    PositionEventIDFactory,
    PositionIDFactory,
    RecommendationIDFactory,
    TradeIntentIDFactory,
    UniverseSnapshotIDFactory,
)
from auto_trading_v2.application.ports.market_calendar import UsEquityMarketCalendar
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
from auto_trading_v2.application.ports.universes import UniverseSnapshotRepository

__all__ = [
    "CandidateRepository",
    "ClientOrderIDFactory",
    "CompletedDailyMarketBarObservation",
    "DailyMarketBarIDFactory",
    "DailyFeaturePipelineItemIDFactory",
    "DailyFeaturePipelineRunIDFactory",
    "DailyFeaturePipelineRunRepository",
    "DailyFeatureScoringItemIDFactory",
    "DailyFeatureScoringRunIDFactory",
    "DailyFeatureScoringRunRepository",
    "DailyMarketDataBatchBudgetPort",
    "DailyMarketDataProviderRole",
    "DailyMarketBarRepository",
    "DailyMarketDataProvider",
    "DecisionIDFactory",
    "FeatureSnapshotIDFactory",
    "FeatureSnapshotRepository",
    "FilterEvaluationIDFactory",
    "FilterEvaluationRepository",
    "FillIDFactory",
    "FetchCompletedDailyBarsRequest",
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
    "UniverseSnapshotIDFactory",
    "UniverseSnapshotRepository",
    "UsEquityMarketCalendar",
]
