"""Commands and insert-only records for the P3 daily feature pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_pipeline import (
    DAILY_FEATURE_PIPELINE_POLICY_V1,
    MIN_REQUESTED_SESSIONS,
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineItem,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelinePolicy,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunStatus,
    DailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
    UniverseSnapshotID,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class RunDailyFeaturePipelineCommand:
    universe_snapshot_id: UniverseSnapshotID
    provider_code: str
    as_of: datetime
    completion_grace: CompletionGracePeriod
    horizon: TradingDayHorizon
    requested_session_count: int = 30
    policy: DailyFeaturePipelinePolicy = DAILY_FEATURE_PIPELINE_POLICY_V1

    def __post_init__(self) -> None:
        if not isinstance(self.universe_snapshot_id, UniverseSnapshotID):
            raise ValueError("universe_snapshot_id is invalid")
        if not isinstance(self.provider_code, str) or not _CODE.fullmatch(
            self.provider_code.strip()
        ):
            raise ValueError("provider_code is invalid")
        if not isinstance(self.completion_grace, CompletionGracePeriod):
            raise ValueError("completion_grace is invalid")
        if not isinstance(self.horizon, TradingDayHorizon):
            raise ValueError("horizon is invalid")
        if not isinstance(self.policy, DailyFeaturePipelinePolicy):
            raise ValueError("daily feature pipeline policy is invalid")
        if (
            isinstance(self.requested_session_count, bool)
            or not isinstance(self.requested_session_count, int)
            or self.requested_session_count < MIN_REQUESTED_SESSIONS
        ):
            raise ValueError("requested_session_count is below the v1 minimum")
        try:
            as_of = normalize_utc(self.as_of)
        except ValidationError:
            raise ValueError("as_of must be timezone-aware") from None
        object.__setattr__(self, "provider_code", self.provider_code.strip())
        object.__setattr__(self, "as_of", as_of)


@dataclass(frozen=True, slots=True)
class NewDailyFeaturePipelineItem:
    daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    ordinal: int
    symbol: Symbol
    mic_code: str
    completed_session_date: SessionDate | None
    outcome: DailyFeaturePipelineItemOutcome
    daily_bar_created_count: int
    daily_bar_existing_count: int
    feature_snapshot_id: FeatureSnapshotID | None
    feature_quality_status: FeatureQualityStatus | None
    safe_reason_code: str | None
    provider_request_count: int
    provider_credit_count: int | None
    started_at: datetime
    finished_at: datetime

    def stored(self, recorded_at: datetime) -> DailyFeaturePipelineItem:
        return DailyFeaturePipelineItem(
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
            recorded_at=recorded_at,
        )

    def digest_payload(self) -> dict[str, object]:
        return self.stored(self.finished_at).digest_payload()


@dataclass(frozen=True, slots=True)
class NewDailyFeaturePipelineRun:
    daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    run_key: str
    content_digest: str
    identity: DailyFeaturePipelineIdentity = field(repr=False)
    status: DailyFeaturePipelineRunStatus
    total_count: int
    ready_count: int
    degraded_count: int
    data_insufficient_count: int
    no_data_count: int
    provider_error_count: int
    calendar_error_count: int
    not_attempted_count: int
    estimated_credit_count: int | None
    consumed_credit_count: int | None
    started_at: datetime
    finished_at: datetime

    def stored(self, recorded_at: datetime) -> DailyFeaturePipelineRun:
        return DailyFeaturePipelineRun(
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
            recorded_at=recorded_at,
        )


@dataclass(frozen=True, slots=True)
class NewDailyFeaturePipelineRunWithItems:
    run: NewDailyFeaturePipelineRun
    items: tuple[NewDailyFeaturePipelineItem, ...] = field(repr=False)

    def stored(self, recorded_at: datetime) -> DailyFeaturePipelineRunWithItems:
        return DailyFeaturePipelineRunWithItems(
            self.run.stored(recorded_at),
            tuple(item.stored(recorded_at) for item in self.items),
        )


class DailyFeaturePipelineExecutionOutcome(StrEnum):
    EXECUTED = "EXECUTED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineExecutionResult:
    outcome: DailyFeaturePipelineExecutionOutcome
    result: DailyFeaturePipelineRunWithItems
