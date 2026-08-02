"""Safe Decimal and row mapping for P4A scoring aggregates."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.feature_scoring import (
    NewDailyFeatureScoringItem,
    NewDailyFeatureScoringRun,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringIdentity,
    DailyFeatureScoringItem,
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRun,
    DailyFeatureScoringRunStatus,
    FeatureScoringPolicyCode,
    FeatureScoringPolicyVersion,
    RankingPolicyCode,
    RankingPolicyVersion,
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


def new_scoring_run_values(run: NewDailyFeatureScoringRun) -> dict[str, object]:
    identity = run.identity
    return {
        "daily_feature_scoring_run_id": run.daily_feature_scoring_run_id.value,
        "scoring_run_key": run.scoring_run_key,
        "content_digest": run.content_digest,
        "source_daily_feature_pipeline_run_id": (
            identity.source_daily_feature_pipeline_run_id.value
        ),
        "scoring_policy_code": identity.scoring_policy_code.value,
        "scoring_policy_version": identity.scoring_policy_version.value,
        "ranking_policy_code": identity.ranking_policy_code.value,
        "ranking_policy_version": identity.ranking_policy_version.value,
        "status": run.status.value,
        "total_count": run.total_count,
        "scored_ready_count": run.scored_ready_count,
        "scored_degraded_count": run.scored_degraded_count,
        "unscorable_count": run.unscorable_count,
        "generated_at": run.generated_at,
    }


def new_scoring_item_values(item: NewDailyFeatureScoringItem) -> dict[str, object]:
    return {
        "daily_feature_scoring_item_id": item.daily_feature_scoring_item_id.value,
        "daily_feature_scoring_run_id": item.daily_feature_scoring_run_id.value,
        "source_daily_feature_pipeline_item_id": (item.source_daily_feature_pipeline_item_id.value),
        "ordinal": item.ordinal,
        "rank": item.rank,
        "symbol": item.symbol.value,
        "mic_code": item.mic_code,
        "feature_snapshot_id": _id_value(item.feature_snapshot_id),
        "source_quality_status": _enum_value(item.source_quality_status),
        "outcome": item.outcome.value,
        "momentum_score": _score_value(item.momentum_score),
        "trend_score": _score_value(item.trend_score),
        "breakout_score": _score_value(item.breakout_score),
        "price_action_score": _score_value(item.price_action_score),
        "stability_score": _score_value(item.stability_score),
        "volume_score": _score_value(item.volume_score),
        "overall_relative_score": _score_value(item.overall_relative_score),
        "safe_reason_code": item.safe_reason_code,
        "generated_at": item.generated_at,
    }


def map_scoring_run(row: Mapping[Any, Any]) -> DailyFeatureScoringRun:
    try:
        identity = DailyFeatureScoringIdentity(
            DailyFeaturePipelineRunID(_uuid(row["source_daily_feature_pipeline_run_id"])),
            FeatureScoringPolicyCode(_string(row["scoring_policy_code"])),
            FeatureScoringPolicyVersion(_string(row["scoring_policy_version"])),
            RankingPolicyCode(_string(row["ranking_policy_code"])),
            RankingPolicyVersion(_string(row["ranking_policy_version"])),
        )
        return DailyFeatureScoringRun(
            DailyFeatureScoringRunID(_uuid(row["daily_feature_scoring_run_id"])),
            _string(row["scoring_run_key"]),
            _string(row["content_digest"]),
            identity,
            DailyFeatureScoringRunStatus(_string(row["status"])),
            _integer(row["total_count"]),
            _integer(row["scored_ready_count"]),
            _integer(row["scored_degraded_count"]),
            _integer(row["unscorable_count"]),
            _datetime(row["generated_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError):
        raise PersistenceMappingError("daily_feature_scoring_run") from None


def map_scoring_item(row: Mapping[Any, Any]) -> DailyFeatureScoringItem:
    try:
        snapshot = row["feature_snapshot_id"]
        quality = row["source_quality_status"]
        reason = row["safe_reason_code"]
        return DailyFeatureScoringItem(
            DailyFeatureScoringItemID(_uuid(row["daily_feature_scoring_item_id"])),
            DailyFeatureScoringRunID(_uuid(row["daily_feature_scoring_run_id"])),
            DailyFeaturePipelineItemID(_uuid(row["source_daily_feature_pipeline_item_id"])),
            _integer(row["ordinal"]),
            _nullable_integer(row["rank"]),
            Symbol(_string(row["symbol"])),
            _string(row["mic_code"]),
            None if snapshot is None else FeatureSnapshotID(_uuid(snapshot)),
            None if quality is None else FeatureQualityStatus(_string(quality)),
            DailyFeatureScoringItemOutcome(_string(row["outcome"])),
            _score(row["momentum_score"]),
            _score(row["trend_score"]),
            _score(row["breakout_score"]),
            _score(row["price_action_score"]),
            _score(row["stability_score"]),
            _score(row["volume_score"]),
            _score(row["overall_relative_score"]),
            None if reason is None else _string(reason),
            _datetime(row["generated_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError):
        raise PersistenceMappingError("daily_feature_scoring_item") from None


def _score(value: object) -> RelativeScore | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise TypeError
    return RelativeScore(value)


def _score_value(value: RelativeScore | None) -> Decimal | None:
    return None if value is None else value.value


def _id_value(value: FeatureSnapshotID | None) -> UUID | None:
    return None if value is None else value.value


def _enum_value(value: FeatureQualityStatus | None) -> str | None:
    return None if value is None else value.value


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
