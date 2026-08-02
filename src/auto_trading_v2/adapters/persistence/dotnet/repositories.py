"""DotNet repository types reusing provider-neutral Core statements and mappings."""

from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyCandidateRepository,
    SqlAlchemyDailyFeaturePipelineRunRepository,
    SqlAlchemyDailyFeatureScoringRunRepository,
    SqlAlchemyDailyMarketBarRepository,
    SqlAlchemyFeatureSnapshotRepository,
    SqlAlchemyFilterEvaluationRepository,
    SqlAlchemyMarketSnapshotRepository,
    SqlAlchemyPaperFillRepository,
    SqlAlchemyPaperOrderRepository,
    SqlAlchemyPaperPositionRepository,
    SqlAlchemyPositionEventRepository,
    SqlAlchemyRecommendationRepository,
    SqlAlchemyStrategyDecisionRepository,
    SqlAlchemyTradeIntentRepository,
    SqlAlchemyUniverseSnapshotRepository,
)


class DotNetMarketSnapshotRepository(SqlAlchemyMarketSnapshotRepository):
    """MarketSnapshot contract backed by the DotNet Core compiler adapter."""


class DotNetDailyMarketBarRepository(SqlAlchemyDailyMarketBarRepository):
    """DailyMarketBar contract backed by the DotNet Core compiler adapter."""


class DotNetFeatureSnapshotRepository(SqlAlchemyFeatureSnapshotRepository):
    """FeatureSnapshot contract backed by the DotNet Core compiler adapter."""


class DotNetUniverseSnapshotRepository(SqlAlchemyUniverseSnapshotRepository):
    """UniverseSnapshot contract backed by the DotNet Core compiler adapter."""


class DotNetDailyFeaturePipelineRunRepository(SqlAlchemyDailyFeaturePipelineRunRepository):
    """Pipeline run contract backed by the DotNet Core compiler adapter."""


class DotNetDailyFeatureScoringRunRepository(SqlAlchemyDailyFeatureScoringRunRepository):
    """Relative-scoring contract backed by the DotNet Core compiler adapter."""


class DotNetRecommendationRepository(SqlAlchemyRecommendationRepository):
    """Recommendation contract backed by the DotNet Core compiler adapter."""


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
    "DotNetDailyMarketBarRepository",
    "DotNetDailyFeaturePipelineRunRepository",
    "DotNetDailyFeatureScoringRunRepository",
    "DotNetFeatureSnapshotRepository",
    "DotNetFilterEvaluationRepository",
    "DotNetMarketSnapshotRepository",
    "DotNetPaperFillRepository",
    "DotNetPaperOrderRepository",
    "DotNetPaperPositionRepository",
    "DotNetPositionEventRepository",
    "DotNetRecommendationRepository",
    "DotNetStrategyDecisionRepository",
    "DotNetTradeIntentRepository",
    "DotNetUniverseSnapshotRepository",
]
