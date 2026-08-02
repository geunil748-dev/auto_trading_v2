"""Commands, results, and insert-only records for P4A relative scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.feature_scoring import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
    DailyFeatureScoringIdentity,
    DailyFeatureScoringItem,
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRun,
    DailyFeatureScoringRunStatus,
    DailyFeatureScoringRunWithItems,
    RelativeScore,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    Symbol,
)


@dataclass(frozen=True, slots=True)
class RunDailyFeatureScoringCommand:
    daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    scoring_policy_code: str = SCORING_POLICY_CODE
    scoring_policy_version: str = SCORING_POLICY_VERSION
    ranking_policy_code: str = RANKING_POLICY_CODE
    ranking_policy_version: str = RANKING_POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.daily_feature_pipeline_run_id, DailyFeaturePipelineRunID):
            raise ValueError("daily_feature_pipeline_run_id is invalid")
        if (
            self.scoring_policy_code,
            self.scoring_policy_version,
            self.ranking_policy_code,
            self.ranking_policy_version,
        ) != (
            SCORING_POLICY_CODE,
            SCORING_POLICY_VERSION,
            RANKING_POLICY_CODE,
            RANKING_POLICY_VERSION,
        ):
            raise ValueError("P4A scoring or ranking policy is unsupported")


@dataclass(frozen=True, slots=True)
class NewDailyFeatureScoringItem:
    daily_feature_scoring_item_id: DailyFeatureScoringItemID
    daily_feature_scoring_run_id: DailyFeatureScoringRunID
    source_daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    ordinal: int
    rank: int | None
    symbol: Symbol
    mic_code: str
    feature_snapshot_id: FeatureSnapshotID | None
    source_quality_status: FeatureQualityStatus | None
    outcome: DailyFeatureScoringItemOutcome
    momentum_score: RelativeScore | None
    trend_score: RelativeScore | None
    breakout_score: RelativeScore | None
    price_action_score: RelativeScore | None
    stability_score: RelativeScore | None
    volume_score: RelativeScore | None
    overall_relative_score: RelativeScore | None
    safe_reason_code: str | None
    generated_at: datetime

    def stored(self, recorded_at: datetime) -> DailyFeatureScoringItem:
        return DailyFeatureScoringItem(
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
            recorded_at=recorded_at,
        )


@dataclass(frozen=True, slots=True)
class NewDailyFeatureScoringRun:
    daily_feature_scoring_run_id: DailyFeatureScoringRunID
    scoring_run_key: str
    content_digest: str
    identity: DailyFeatureScoringIdentity = field(repr=False)
    status: DailyFeatureScoringRunStatus
    total_count: int
    scored_ready_count: int
    scored_degraded_count: int
    unscorable_count: int
    generated_at: datetime

    def stored(self, recorded_at: datetime) -> DailyFeatureScoringRun:
        return DailyFeatureScoringRun(
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
            recorded_at=recorded_at,
        )


@dataclass(frozen=True, slots=True)
class NewDailyFeatureScoringRunWithItems:
    run: NewDailyFeatureScoringRun
    items: tuple[NewDailyFeatureScoringItem, ...] = field(repr=False)

    def stored(self, recorded_at: datetime) -> DailyFeatureScoringRunWithItems:
        return DailyFeatureScoringRunWithItems(
            self.run.stored(recorded_at),
            tuple(item.stored(recorded_at) for item in self.items),
        )


class DailyFeatureScoringExecutionOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    SOURCE_RUN_NOT_FOUND = "SOURCE_RUN_NOT_FOUND"
    SOURCE_RUN_NOT_ELIGIBLE = "SOURCE_RUN_NOT_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringExecutionResult:
    outcome: DailyFeatureScoringExecutionOutcome
    result: DailyFeatureScoringRunWithItems | None
    safe_reason_code: str | None = None

    def __post_init__(self) -> None:
        succeeded = self.outcome in {
            DailyFeatureScoringExecutionOutcome.CREATED,
            DailyFeatureScoringExecutionOutcome.ALREADY_EXISTS,
        }
        if succeeded != (self.result is not None) or succeeded == (
            self.safe_reason_code is not None
        ):
            raise ValueError("daily feature scoring result shape is invalid")
