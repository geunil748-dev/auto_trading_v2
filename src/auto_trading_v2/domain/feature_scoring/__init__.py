"""Public P4A transparent relative-scoring domain surface."""

from auto_trading_v2.domain.feature_scoring.aggregate import (
    DailyFeatureScoringRunWithItems,
    daily_feature_scoring_content_digest,
)
from auto_trading_v2.domain.feature_scoring.errors import FeatureScoringValidationError
from auto_trading_v2.domain.feature_scoring.identity import (
    DailyFeatureScoringIdentity,
    daily_feature_scoring_run_key,
    feature_scoring_content_digest,
)
from auto_trading_v2.domain.feature_scoring.models import (
    DailyFeatureScoringItem,
    DailyFeatureScoringRun,
    RelativeScore,
)
from auto_trading_v2.domain.feature_scoring.outcomes import (
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRunStatus,
)
from auto_trading_v2.domain.feature_scoring.policies import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
    FeatureScoringPolicyCode,
    FeatureScoringPolicyVersion,
    RankingPolicyCode,
    RankingPolicyVersion,
    fixed_policy_values,
)
from auto_trading_v2.domain.feature_scoring.scoring import (
    CalculatedComponentScores,
    RankingInput,
    ValidatedTechnicalFeatures,
    ascending_midrank_percentiles,
    calculate_component_scores,
    deterministic_ranks,
    parse_v1_technical_features,
)

__all__ = [
    "CalculatedComponentScores",
    "DailyFeatureScoringIdentity",
    "DailyFeatureScoringItem",
    "DailyFeatureScoringItemOutcome",
    "DailyFeatureScoringRun",
    "DailyFeatureScoringRunStatus",
    "DailyFeatureScoringRunWithItems",
    "FeatureScoringPolicyCode",
    "FeatureScoringPolicyVersion",
    "FeatureScoringValidationError",
    "RANKING_POLICY_CODE",
    "RANKING_POLICY_VERSION",
    "RankingInput",
    "RankingPolicyCode",
    "RankingPolicyVersion",
    "RelativeScore",
    "SCORING_POLICY_CODE",
    "SCORING_POLICY_VERSION",
    "ValidatedTechnicalFeatures",
    "ascending_midrank_percentiles",
    "calculate_component_scores",
    "daily_feature_scoring_content_digest",
    "daily_feature_scoring_run_key",
    "deterministic_ranks",
    "feature_scoring_content_digest",
    "fixed_policy_values",
    "parse_v1_technical_features",
]
