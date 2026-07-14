"""SQLAlchemy Core repositories for the first persistence slice."""

from auto_trading_v2.adapters.persistence.repositories.candidates import (
    SqlAlchemyCandidateRepository,
)
from auto_trading_v2.adapters.persistence.repositories.filter_evaluations import (
    SqlAlchemyFilterEvaluationRepository,
)
from auto_trading_v2.adapters.persistence.repositories.market_snapshots import (
    SqlAlchemyMarketSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.repositories.strategy_decisions import (
    SqlAlchemyStrategyDecisionRepository,
)

__all__ = [
    "SqlAlchemyCandidateRepository",
    "SqlAlchemyFilterEvaluationRepository",
    "SqlAlchemyMarketSnapshotRepository",
    "SqlAlchemyStrategyDecisionRepository",
]
