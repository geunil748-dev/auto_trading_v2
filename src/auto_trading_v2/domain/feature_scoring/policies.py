"""Frozen policy identifiers for P4A transparent relative scoring."""

from dataclasses import dataclass

from auto_trading_v2.domain.feature_scoring.errors import FeatureScoringValidationError

SCORING_POLICY_CODE = "US_EQUITY_DAILY_TECHNICAL_RELATIVE_SCORE"
SCORING_POLICY_VERSION = "v1"
RANKING_POLICY_CODE = "QUALITY_TIERED_CROSS_SECTIONAL_PERCENTILE"
RANKING_POLICY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class _PolicyValue:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value:
            raise FeatureScoringValidationError("SCORING_POLICY_VALUE_INVALID")


class FeatureScoringPolicyCode(_PolicyValue):
    __slots__ = ()


class FeatureScoringPolicyVersion(_PolicyValue):
    __slots__ = ()


class RankingPolicyCode(_PolicyValue):
    __slots__ = ()


class RankingPolicyVersion(_PolicyValue):
    __slots__ = ()


def fixed_policy_values() -> tuple[
    FeatureScoringPolicyCode,
    FeatureScoringPolicyVersion,
    RankingPolicyCode,
    RankingPolicyVersion,
]:
    return (
        FeatureScoringPolicyCode(SCORING_POLICY_CODE),
        FeatureScoringPolicyVersion(SCORING_POLICY_VERSION),
        RankingPolicyCode(RANKING_POLICY_CODE),
        RankingPolicyVersion(RANKING_POLICY_VERSION),
    )
