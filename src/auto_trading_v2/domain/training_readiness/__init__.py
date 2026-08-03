"""Read-only evidence contracts for prediction training readiness."""

from auto_trading_v2.domain.training_readiness.evaluation import (
    calculate_percentage,
    evaluate_legacy_calibration_readiness,
    included_dataset_facts,
)
from auto_trading_v2.domain.training_readiness.models import (
    DataQualityDecisionEvidence,
    DatasetIdentityFacts,
    HorizonAuditGroup,
    IncludedDatasetFacts,
    LegacyCalibrationReadinessResult,
    MvpTradeModelReadinessResult,
    NamedCount,
    PercentageFact,
    ProviderQualityDistribution,
    TrainingReadinessAuditBatchResult,
    TrainingReadinessAuditResult,
    UpstreamQualityFacts,
)
from auto_trading_v2.domain.training_readiness.outcomes import (
    COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE,
    EXCLUSION_REASON_ORDER,
    LEGACY_RESEARCH_LIMITATION,
    MVP_TRADE_MODEL_BLOCKERS,
    NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
    PRICE_ONLY_V2_INELIGIBILITY_REASON_ORDER,
    LegacyCalibrationReadiness,
    MvpTradeModelReadiness,
    PercentageStatus,
)

__all__ = [
    "COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE",
    "DataQualityDecisionEvidence",
    "DatasetIdentityFacts",
    "EXCLUSION_REASON_ORDER",
    "HorizonAuditGroup",
    "IncludedDatasetFacts",
    "LEGACY_RESEARCH_LIMITATION",
    "LegacyCalibrationReadiness",
    "LegacyCalibrationReadinessResult",
    "MVP_TRADE_MODEL_BLOCKERS",
    "MvpTradeModelReadiness",
    "MvpTradeModelReadinessResult",
    "NOT_DERIVABLE_FROM_CURRENT_SCHEMA",
    "PRICE_ONLY_V2_INELIGIBILITY_REASON_ORDER",
    "NamedCount",
    "PercentageFact",
    "PercentageStatus",
    "ProviderQualityDistribution",
    "TrainingReadinessAuditBatchResult",
    "TrainingReadinessAuditResult",
    "UpstreamQualityFacts",
    "calculate_percentage",
    "evaluate_legacy_calibration_readiness",
    "included_dataset_facts",
]
