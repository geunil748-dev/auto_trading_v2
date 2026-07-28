"""Immutable application boundary contracts."""

from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    DailyMarketBarCreationOutcome,
    DailyMarketBarCreationResult,
    NewDailyMarketBar,
)
from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    FeatureSnapshotCreationOutcome,
    FeatureSnapshotCreationResult,
    NewFeatureSnapshot,
)
from auto_trading_v2.application.contracts.paper_fills import (
    NewPaperFill,
    PaperFillExecutionResult,
    PaperOrderFillTransition,
    StoredPaperFill,
)
from auto_trading_v2.application.contracts.paper_orders import (
    NewPaperOrder,
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
    StoredPaperOrder,
)
from auto_trading_v2.application.contracts.persistence import (
    JSONValue,
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
    StoredCandidate,
    StoredFilterEvaluation,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.contracts.position_exit_decisions import (
    PositionExitDecisionOutcome,
    PositionExitDecisionResult,
)
from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
    PositionProjectionResult,
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.recommendations import (
    CreateRecommendationCommand,
    NewRecommendation,
    RecommendationCreationOutcome,
    RecommendationCreationResult,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    NewPositionStrategyDecision,
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyFeatureCommand,
    TwelveDataDailyFeatureResult,
    TwelveDataDailyMarketBarIngestionCommand,
    TwelveDataIngestionOutcome,
    TwelveDataIngestionResult,
    TwelveDataIngestionSummary,
)

__all__ = [
    "JSONValue",
    "CreateDailyMarketBarCommand",
    "CreateFeatureSnapshotCommand",
    "CreateRecommendationCommand",
    "FeatureSnapshotCreationOutcome",
    "FeatureSnapshotCreationResult",
    "DailyMarketBarCreationOutcome",
    "DailyMarketBarCreationResult",
    "NewCandidate",
    "NewDailyMarketBar",
    "NewCandidateStrategyDecision",
    "NewPositionStrategyDecision",
    "NewFilterEvaluation",
    "NewFeatureSnapshot",
    "NewMarketSnapshot",
    "NewRecommendation",
    "NewPaperOrder",
    "NewPaperFill",
    "NewPaperPosition",
    "NewPositionEvent",
    "NewTradeIntent",
    "PaperOrderSubmissionRequest",
    "PaperOrderSubmissionResult",
    "PaperFillExecutionResult",
    "PaperOrderFillTransition",
    "PaperPositionBuyTransition",
    "PositionProjectionResult",
    "RecommendationCreationOutcome",
    "RecommendationCreationResult",
    "PositionExitDecisionOutcome",
    "PositionExitDecisionResult",
    "StoredCandidate",
    "StoredCandidateStrategyDecision",
    "StoredPositionStrategyDecision",
    "StoredFilterEvaluation",
    "StoredMarketSnapshot",
    "StoredPaperOrder",
    "StoredPaperFill",
    "StoredPaperPosition",
    "StoredPositionEvent",
    "StoredTradeIntent",
    "TwelveDataDailyMarketBarIngestionCommand",
    "TwelveDataDailyFeatureCommand",
    "TwelveDataDailyFeatureResult",
    "TwelveDataIngestionOutcome",
    "TwelveDataIngestionResult",
    "TwelveDataIngestionSummary",
]
