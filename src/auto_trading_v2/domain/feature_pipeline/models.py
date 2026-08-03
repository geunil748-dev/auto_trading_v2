"""Immutable canonical daily feature pipeline run and item records."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import NoReturn

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_pipeline.errors import (
    DailyFeaturePipelineValidationError,
)
from auto_trading_v2.domain.feature_pipeline.identity import (
    DailyFeaturePipelineIdentity,
    daily_feature_run_key,
    pipeline_content_digest,
)
from auto_trading_v2.domain.feature_pipeline.outcomes import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_RUN_KEY = re.compile(r"^daily-feature-run:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineItem:
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
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.daily_feature_pipeline_item_id, DailyFeaturePipelineItemID):
            _invalid("PIPELINE_ITEM_ID_INVALID")
        if not isinstance(self.daily_feature_pipeline_run_id, DailyFeaturePipelineRunID):
            _invalid("PIPELINE_RUN_ID_INVALID")
        if (
            not isinstance(self.ordinal, int)
            or isinstance(self.ordinal, bool)
            or not 1 <= self.ordinal <= 100
        ):
            _invalid("PIPELINE_ITEM_ORDINAL_INVALID")
        if not isinstance(self.symbol, Symbol):
            _invalid("PIPELINE_ITEM_SYMBOL_INVALID")
        if self.mic_code not in {"XNGS", "XNGM", "XNCM", "XNYS", "XASE"}:
            _invalid("PIPELINE_ITEM_MIC_INVALID")
        if self.completed_session_date is not None and not isinstance(
            self.completed_session_date, SessionDate
        ):
            _invalid("PIPELINE_ITEM_SESSION_INVALID")
        if not isinstance(self.outcome, DailyFeaturePipelineItemOutcome):
            _invalid("PIPELINE_ITEM_OUTCOME_INVALID")
        for value in (
            self.daily_bar_created_count,
            self.daily_bar_existing_count,
            self.provider_request_count,
        ):
            _nonnegative(value, "PIPELINE_ITEM_COUNT_INVALID")
        if self.provider_credit_count is not None:
            _nonnegative(self.provider_credit_count, "PIPELINE_ITEM_CREDIT_INVALID")
        if self.safe_reason_code is not None and not _REASON.fullmatch(self.safe_reason_code):
            _invalid("PIPELINE_ITEM_REASON_INVALID")
        expected_quality = {
            DailyFeaturePipelineItemOutcome.READY: FeatureQualityStatus.READY,
            DailyFeaturePipelineItemOutcome.DEGRADED: FeatureQualityStatus.DEGRADED,
        }.get(self.outcome)
        if expected_quality is None:
            if self.feature_snapshot_id is not None or self.feature_quality_status is not None:
                _invalid("PIPELINE_ITEM_FAILURE_SHAPE_INVALID")
        elif (
            self.feature_snapshot_id is None or self.feature_quality_status is not expected_quality
        ):
            _invalid("PIPELINE_ITEM_FEATURE_SHAPE_INVALID")
        started = _timestamp(self.started_at, "PIPELINE_ITEM_STARTED_AT_INVALID")
        finished = _timestamp(self.finished_at, "PIPELINE_ITEM_FINISHED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "PIPELINE_ITEM_RECORDED_AT_INVALID")
        if started > finished or finished > recorded:
            _invalid("PIPELINE_ITEM_TIME_ORDER_INVALID")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)
        object.__setattr__(self, "recorded_at", recorded)

    def digest_payload(self) -> dict[str, object]:
        return {
            "completed_session_date": None
            if self.completed_session_date is None
            else self.completed_session_date.serialize(),
            "daily_bar_created_count": self.daily_bar_created_count,
            "daily_bar_existing_count": self.daily_bar_existing_count,
            "feature_quality_status": None
            if self.feature_quality_status is None
            else self.feature_quality_status.value,
            "feature_snapshot_id": None
            if self.feature_snapshot_id is None
            else self.feature_snapshot_id.serialize(),
            "mic_code": self.mic_code,
            "ordinal": self.ordinal,
            "outcome": self.outcome.value,
            "provider_credit_count": self.provider_credit_count,
            "provider_request_count": self.provider_request_count,
            "safe_reason_code": self.safe_reason_code,
            "symbol": self.symbol.serialize(),
        }


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineRun:
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
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.daily_feature_pipeline_run_id, DailyFeaturePipelineRunID):
            _invalid("PIPELINE_RUN_ID_INVALID")
        if not _RUN_KEY.fullmatch(self.run_key) or self.run_key != daily_feature_run_key(
            self.identity
        ):
            _invalid("PIPELINE_RUN_KEY_INVALID")
        if not _DIGEST.fullmatch(self.content_digest):
            _invalid("PIPELINE_RUN_DIGEST_INVALID")
        if not isinstance(self.status, DailyFeaturePipelineRunStatus):
            _invalid("PIPELINE_RUN_STATUS_INVALID")
        counts = self.outcome_counts
        for value in (self.total_count, *counts):
            _nonnegative(value, "PIPELINE_RUN_COUNT_INVALID")
        if self.total_count != sum(counts):
            _invalid("PIPELINE_RUN_COUNT_SUM_INVALID")
        for credit in (self.estimated_credit_count, self.consumed_credit_count):
            if credit is not None:
                _nonnegative(credit, "PIPELINE_RUN_CREDIT_INVALID")
        started = _timestamp(self.started_at, "PIPELINE_RUN_STARTED_AT_INVALID")
        finished = _timestamp(self.finished_at, "PIPELINE_RUN_FINISHED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "PIPELINE_RUN_RECORDED_AT_INVALID")
        if started > finished or finished > recorded:
            _invalid("PIPELINE_RUN_TIME_ORDER_INVALID")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)
        object.__setattr__(self, "recorded_at", recorded)

    @property
    def outcome_counts(self) -> tuple[int, ...]:
        return (
            self.ready_count,
            self.degraded_count,
            self.data_insufficient_count,
            self.no_data_count,
            self.provider_error_count,
            self.calendar_error_count,
            self.not_attempted_count,
        )


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineRunWithItems:
    run: DailyFeaturePipelineRun
    items: tuple[DailyFeaturePipelineItem, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.items) != self.run.total_count:
            _invalid("PIPELINE_ITEM_TOTAL_MISMATCH")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _invalid("PIPELINE_ITEM_ORDER_INVALID")
        if any(
            item.daily_feature_pipeline_run_id != self.run.daily_feature_pipeline_run_id
            for item in self.items
        ):
            _invalid("PIPELINE_ITEM_RUN_MISMATCH")
        if len({item.symbol for item in self.items}) != len(self.items):
            _invalid("PIPELINE_ITEM_SYMBOL_DUPLICATE")
        if self.run.content_digest != daily_feature_pipeline_content_digest(self.run, self.items):
            _invalid("PIPELINE_RUN_DIGEST_MISMATCH")


def daily_feature_pipeline_content_digest(
    run: DailyFeaturePipelineRun,
    items: tuple[DailyFeaturePipelineItem, ...],
) -> str:
    payload: dict[str, object] = {
        "calendar_code": run.identity.calendar_code.value,
        "calendar_version": run.identity.calendar_version.value,
        "completed_session_date": None
        if run.identity.completed_session_date is None
        else run.identity.completed_session_date.serialize(),
        "consumed_credit_count": run.consumed_credit_count,
        "counts": {
            "calendar_error": run.calendar_error_count,
            "data_insufficient": run.data_insufficient_count,
            "degraded": run.degraded_count,
            "no_data": run.no_data_count,
            "not_attempted": run.not_attempted_count,
            "provider_error": run.provider_error_count,
            "ready": run.ready_count,
            "total": run.total_count,
        },
        "estimated_credit_count": run.estimated_credit_count,
        "items": [item.digest_payload() for item in items],
        "provider_request_count": sum(item.provider_request_count for item in items),
        "status": run.status.value,
    }
    if run.identity.pipeline_version != "v1":
        payload["policy"] = {
            "feature_set_code": run.identity.feature_set_code,
            "feature_set_version": run.identity.feature_set_version,
            "pipeline_code": run.identity.pipeline_code,
            "pipeline_version": run.identity.pipeline_version,
        }
    return pipeline_content_digest(payload)


def _nonnegative(value: object, category: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _invalid(category)


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        _invalid(category)


def _invalid(category: str) -> NoReturn:
    raise DailyFeaturePipelineValidationError(category)
