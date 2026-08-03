"""Safe row mapping for canonical daily feature pipeline runs and items."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineItem,
    NewDailyFeaturePipelineRun,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineItem,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunStatus,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.market_calendar import (
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
    UniverseSnapshotID,
)


def new_pipeline_run_values(run: NewDailyFeaturePipelineRun) -> dict[str, object]:
    source = run.identity
    return {
        "daily_feature_pipeline_run_id": run.daily_feature_pipeline_run_id.value,
        "run_key": run.run_key,
        "content_digest": run.content_digest,
        "universe_snapshot_id": source.universe_snapshot_id.value,
        "pipeline_code": source.pipeline_code,
        "pipeline_version": source.pipeline_version,
        "provider_code": source.provider_code,
        "calendar_code": source.calendar_code.value,
        "calendar_version": source.calendar_version.value,
        "completed_session_date": None
        if source.completed_session_date is None
        else source.completed_session_date.value,
        "as_of": source.as_of,
        "completion_grace_seconds": int(source.completion_grace.value.total_seconds()),
        "adjustment_basis": source.adjustment_basis.value,
        "feature_set_code": source.feature_set_code,
        "feature_set_version": source.feature_set_version,
        "horizon_trading_days": source.horizon.value,
        "requested_session_count": source.requested_session_count,
        "status": run.status.value,
        "total_count": run.total_count,
        "ready_count": run.ready_count,
        "degraded_count": run.degraded_count,
        "data_insufficient_count": run.data_insufficient_count,
        "no_data_count": run.no_data_count,
        "provider_error_count": run.provider_error_count,
        "calendar_error_count": run.calendar_error_count,
        "not_attempted_count": run.not_attempted_count,
        "estimated_credit_count": run.estimated_credit_count,
        "consumed_credit_count": run.consumed_credit_count,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def new_pipeline_item_values(item: NewDailyFeaturePipelineItem) -> dict[str, object]:
    return {
        "daily_feature_pipeline_item_id": item.daily_feature_pipeline_item_id.value,
        "daily_feature_pipeline_run_id": item.daily_feature_pipeline_run_id.value,
        "ordinal": item.ordinal,
        "symbol": item.symbol.value,
        "mic_code": item.mic_code,
        "completed_session_date": None
        if item.completed_session_date is None
        else item.completed_session_date.value,
        "outcome": item.outcome.value,
        "daily_bar_created_count": item.daily_bar_created_count,
        "daily_bar_existing_count": item.daily_bar_existing_count,
        "feature_snapshot_id": None
        if item.feature_snapshot_id is None
        else item.feature_snapshot_id.value,
        "feature_quality_status": None
        if item.feature_quality_status is None
        else item.feature_quality_status.value,
        "safe_reason_code": item.safe_reason_code,
        "provider_request_count": item.provider_request_count,
        "provider_credit_count": item.provider_credit_count,
        "started_at": item.started_at,
        "finished_at": item.finished_at,
    }


def map_pipeline_run(row: Mapping[Any, Any]) -> DailyFeaturePipelineRun:
    try:
        identity = DailyFeaturePipelineIdentity(
            universe_snapshot_id=UniverseSnapshotID(_uuid(row["universe_snapshot_id"])),
            provider_code=_string(row["provider_code"]),
            calendar_code=ExchangeCalendarCode(_string(row["calendar_code"])),
            calendar_version=ExchangeCalendarVersion(_string(row["calendar_version"])),
            completed_session_date=_session(row["completed_session_date"]),
            adjustment_basis=DailyMarketBarAdjustmentBasis(_string(row["adjustment_basis"])),
            horizon=TradingDayHorizon(_integer(row["horizon_trading_days"])),
            requested_session_count=_integer(row["requested_session_count"]),
            as_of=_datetime(row["as_of"]),
            completion_grace=CompletionGracePeriod(
                timedelta(seconds=_integer(row["completion_grace_seconds"]))
            ),
            pipeline_code=_string(row["pipeline_code"]),
            pipeline_version=_string(row["pipeline_version"]),
            feature_set_code=_string(row["feature_set_code"]),
            feature_set_version=_string(row["feature_set_version"]),
        )
        return DailyFeaturePipelineRun(
            DailyFeaturePipelineRunID(_uuid(row["daily_feature_pipeline_run_id"])),
            _string(row["run_key"]),
            _string(row["content_digest"]),
            identity,
            DailyFeaturePipelineRunStatus(_string(row["status"])),
            _integer(row["total_count"]),
            _integer(row["ready_count"]),
            _integer(row["degraded_count"]),
            _integer(row["data_insufficient_count"]),
            _integer(row["no_data_count"]),
            _integer(row["provider_error_count"]),
            _integer(row["calendar_error_count"]),
            _integer(row["not_attempted_count"]),
            _nullable_integer(row["estimated_credit_count"]),
            _nullable_integer(row["consumed_credit_count"]),
            _datetime(row["started_at"]),
            _datetime(row["finished_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError):
        raise PersistenceMappingError("daily_feature_pipeline_run") from None


def map_pipeline_item(row: Mapping[Any, Any]) -> DailyFeaturePipelineItem:
    try:
        snapshot = row["feature_snapshot_id"]
        quality = row["feature_quality_status"]
        reason = row["safe_reason_code"]
        return DailyFeaturePipelineItem(
            DailyFeaturePipelineItemID(_uuid(row["daily_feature_pipeline_item_id"])),
            DailyFeaturePipelineRunID(_uuid(row["daily_feature_pipeline_run_id"])),
            _integer(row["ordinal"]),
            Symbol(_string(row["symbol"])),
            _string(row["mic_code"]),
            _session(row["completed_session_date"]),
            DailyFeaturePipelineItemOutcome(_string(row["outcome"])),
            _integer(row["daily_bar_created_count"]),
            _integer(row["daily_bar_existing_count"]),
            None if snapshot is None else FeatureSnapshotID(_uuid(snapshot)),
            None if quality is None else FeatureQualityStatus(_string(quality)),
            None if reason is None else _string(reason),
            _integer(row["provider_request_count"]),
            _nullable_integer(row["provider_credit_count"]),
            _datetime(row["started_at"]),
            _datetime(row["finished_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError):
        raise PersistenceMappingError("daily_feature_pipeline_item") from None


def _session(value: object) -> SessionDate | None:
    if value is None:
        return None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError
    return SessionDate(value)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _nullable_integer(value: object) -> int | None:
    return None if value is None else _integer(value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value
