"""Immutable application boundary contracts."""

from auto_trading_v2.application.contracts.alpaca_ingestion import (
    AlpacaDailyMarketBarIngestionCommand,
    AlpacaIngestionOutcome,
    AlpacaIngestionResult,
    AlpacaIngestionSummary,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
    CreateProbabilityCalibrationDatasetCommand,
    NewProbabilityCalibrationDatasetWithItems,
    ProbabilityCalibrationDatasetCreationOutcome,
    ProbabilityCalibrationDatasetCreationResult,
)
from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationOutcome,
    CompletedDailyBarsRequestCreationResult,
)
from auto_trading_v2.application.contracts.daily_bar_comparison import (
    CompareDailyBarProvidersCommand,
    DailyBarProviderComparisonOutcome,
    DailyBarProviderComparisonReport,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    DailyFeaturePipelineExecutionOutcome,
    DailyFeaturePipelineExecutionResult,
    NewDailyFeaturePipelineItem,
    NewDailyFeaturePipelineRun,
    NewDailyFeaturePipelineRunWithItems,
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    DailyMarketBarCreationOutcome,
    DailyMarketBarCreationResult,
    NewDailyMarketBar,
)
from auto_trading_v2.application.contracts.feature_outcomes import (
    DailyFeatureOutcomeObservationExecutionOutcome,
    DailyFeatureOutcomeObservationExecutionResult,
    NewDailyFeatureOutcome,
    NewDailyFeatureOutcomeObservationRunWithItems,
    ObserveDailyFeatureScoringOutcomesCommand,
)
from auto_trading_v2.application.contracts.feature_scoring import (
    DailyFeatureScoringExecutionOutcome,
    DailyFeatureScoringExecutionResult,
    NewDailyFeatureScoringItem,
    NewDailyFeatureScoringRun,
    NewDailyFeatureScoringRunWithItems,
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    FeatureSnapshotCreationOutcome,
    FeatureSnapshotCreationResult,
    NewFeatureSnapshot,
)
from auto_trading_v2.application.contracts.outcome_labels import (
    CreateDailyFeatureOutcomeLabelCommand,
    DailyFeatureOutcomeLabelCreationOutcome,
    DailyFeatureOutcomeLabelCreationResult,
    NewDailyFeatureOutcomeLabel,
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
from auto_trading_v2.application.contracts.training_readiness import (
    RunTrainingReadinessAuditBatchCommand,
    RunTrainingReadinessAuditCommand,
    TrainingReadinessLineageRecord,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyFeatureCommand,
    TwelveDataDailyFeatureResult,
    TwelveDataDailyMarketBarIngestionCommand,
    TwelveDataIngestionOutcome,
    TwelveDataIngestionResult,
    TwelveDataIngestionSummary,
)
from auto_trading_v2.application.contracts.universes import (
    CreateUniverseSnapshotCommand,
    NewUniverseSnapshot,
    UniverseSnapshotCreationOutcome,
    UniverseSnapshotCreationResult,
)

__all__ = [
    "AlpacaDailyMarketBarIngestionCommand",
    "AlpacaIngestionOutcome",
    "AlpacaIngestionResult",
    "AlpacaIngestionSummary",
    "CompareDailyBarProvidersCommand",
    "CalibrationDatasetSourceRecord",
    "CompletedDailyBarsRequestCreationOutcome",
    "CompletedDailyBarsRequestCreationResult",
    "JSONValue",
    "CreateDailyMarketBarCommand",
    "CreateDailyFeatureOutcomeLabelCommand",
    "CreateProbabilityCalibrationDatasetCommand",
    "CreateFeatureSnapshotCommand",
    "CreateRecommendationCommand",
    "FeatureSnapshotCreationOutcome",
    "FeatureSnapshotCreationResult",
    "DailyMarketBarCreationOutcome",
    "DailyMarketBarCreationResult",
    "DailyFeaturePipelineExecutionOutcome",
    "DailyFeaturePipelineExecutionResult",
    "DailyFeatureScoringExecutionOutcome",
    "DailyFeatureScoringExecutionResult",
    "DailyFeatureOutcomeObservationExecutionOutcome",
    "DailyFeatureOutcomeObservationExecutionResult",
    "DailyFeatureOutcomeLabelCreationOutcome",
    "DailyFeatureOutcomeLabelCreationResult",
    "DailyBarProviderComparisonOutcome",
    "DailyBarProviderComparisonReport",
    "NewCandidate",
    "NewDailyMarketBar",
    "NewDailyFeaturePipelineItem",
    "NewDailyFeaturePipelineRun",
    "NewDailyFeaturePipelineRunWithItems",
    "NewDailyFeatureScoringItem",
    "NewDailyFeatureScoringRun",
    "NewDailyFeatureScoringRunWithItems",
    "NewDailyFeatureOutcome",
    "NewDailyFeatureOutcomeObservationRunWithItems",
    "NewDailyFeatureOutcomeLabel",
    "NewProbabilityCalibrationDatasetWithItems",
    "ObserveDailyFeatureScoringOutcomesCommand",
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
    "ProbabilityCalibrationDatasetCreationOutcome",
    "ProbabilityCalibrationDatasetCreationResult",
    "RecommendationCreationOutcome",
    "RecommendationCreationResult",
    "RunDailyFeaturePipelineCommand",
    "RunDailyFeatureScoringCommand",
    "RunTrainingReadinessAuditBatchCommand",
    "RunTrainingReadinessAuditCommand",
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
    "TrainingReadinessLineageRecord",
    "TwelveDataDailyMarketBarIngestionCommand",
    "TwelveDataDailyFeatureCommand",
    "TwelveDataDailyFeatureResult",
    "TwelveDataIngestionOutcome",
    "TwelveDataIngestionResult",
    "TwelveDataIngestionSummary",
    "CreateUniverseSnapshotCommand",
    "NewUniverseSnapshot",
    "UniverseSnapshotCreationOutcome",
    "UniverseSnapshotCreationResult",
]
