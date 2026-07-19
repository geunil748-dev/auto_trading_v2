"""DotNet repository types reusing provider-neutral Core statements and mappings."""

from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyCandidateRepository,
    SqlAlchemyFilterEvaluationRepository,
    SqlAlchemyMarketSnapshotRepository,
    SqlAlchemyPaperFillRepository,
    SqlAlchemyPaperOrderRepository,
    SqlAlchemyPaperPositionRepository,
    SqlAlchemyPositionEventRepository,
    SqlAlchemyStrategyDecisionRepository,
    SqlAlchemyTradeIntentRepository,
)


class DotNetMarketSnapshotRepository(SqlAlchemyMarketSnapshotRepository):
    """MarketSnapshot contract backed by the DotNet Core compiler adapter."""


class DotNetCandidateRepository(SqlAlchemyCandidateRepository):
    """Candidate contract backed by the DotNet Core compiler adapter."""


class DotNetFilterEvaluationRepository(SqlAlchemyFilterEvaluationRepository):
    """FilterEvaluation contract backed by the DotNet Core compiler adapter."""


class DotNetStrategyDecisionRepository(SqlAlchemyStrategyDecisionRepository):
    """StrategyDecision contract backed by the DotNet Core compiler adapter."""


class DotNetTradeIntentRepository(SqlAlchemyTradeIntentRepository):
    """TradeIntent contract backed by the DotNet Core compiler adapter."""


class DotNetPaperOrderRepository(SqlAlchemyPaperOrderRepository):
    """PaperOrder contract backed by the DotNet Core compiler adapter."""


class DotNetPaperFillRepository(SqlAlchemyPaperFillRepository):
    """PaperFill contract backed by the DotNet Core compiler adapter."""


class DotNetPaperPositionRepository(SqlAlchemyPaperPositionRepository):
    """PaperPosition contract backed by the DotNet Core compiler adapter."""


class DotNetPositionEventRepository(SqlAlchemyPositionEventRepository):
    """PositionEvent contract backed by the DotNet Core compiler adapter."""


__all__ = [
    "DotNetCandidateRepository",
    "DotNetFilterEvaluationRepository",
    "DotNetMarketSnapshotRepository",
    "DotNetPaperFillRepository",
    "DotNetPaperOrderRepository",
    "DotNetPaperPositionRepository",
    "DotNetPositionEventRepository",
    "DotNetStrategyDecisionRepository",
    "DotNetTradeIntentRepository",
]
