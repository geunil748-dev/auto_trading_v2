"""SQLAlchemy Core repositories for the first persistence slice."""

from auto_trading_v2.adapters.persistence.repositories.candidates import (
    SqlAlchemyCandidateRepository,
)
from auto_trading_v2.adapters.persistence.repositories.feature_snapshots import (
    SqlAlchemyFeatureSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.repositories.filter_evaluations import (
    SqlAlchemyFilterEvaluationRepository,
)
from auto_trading_v2.adapters.persistence.repositories.market_snapshots import (
    SqlAlchemyMarketSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.repositories.paper_fills import (
    SqlAlchemyPaperFillRepository,
)
from auto_trading_v2.adapters.persistence.repositories.paper_orders import (
    SqlAlchemyPaperOrderRepository,
)
from auto_trading_v2.adapters.persistence.repositories.paper_positions import (
    SqlAlchemyPaperPositionRepository,
)
from auto_trading_v2.adapters.persistence.repositories.position_events import (
    SqlAlchemyPositionEventRepository,
)
from auto_trading_v2.adapters.persistence.repositories.recommendations import (
    SqlAlchemyRecommendationRepository,
)
from auto_trading_v2.adapters.persistence.repositories.strategy_decisions import (
    SqlAlchemyStrategyDecisionRepository,
)
from auto_trading_v2.adapters.persistence.repositories.trade_intents import (
    SqlAlchemyTradeIntentRepository,
)

__all__ = [
    "SqlAlchemyCandidateRepository",
    "SqlAlchemyFilterEvaluationRepository",
    "SqlAlchemyFeatureSnapshotRepository",
    "SqlAlchemyMarketSnapshotRepository",
    "SqlAlchemyPaperOrderRepository",
    "SqlAlchemyPaperFillRepository",
    "SqlAlchemyPaperPositionRepository",
    "SqlAlchemyPositionEventRepository",
    "SqlAlchemyRecommendationRepository",
    "SqlAlchemyStrategyDecisionRepository",
    "SqlAlchemyTradeIntentRepository",
]
