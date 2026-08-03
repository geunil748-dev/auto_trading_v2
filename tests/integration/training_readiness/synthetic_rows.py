from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal

from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    SOURCE_PROVIDER_CODE,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.feature_scoring import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    UniverseSnapshotID,
)
from tests.integration.training_readiness.synthetic_outcome_rows import (
    label_row,
    outcome_row,
)


def append_ready_rows(
    rows: dict[str, list[dict[str, object]]],
    run_ids: tuple[DailyFeaturePipelineRunID, DailyFeatureScoringRunID, UniverseSnapshotID],
    item_ids: tuple[
        FeatureSnapshotID,
        DailyFeaturePipelineItemID,
        DailyFeatureScoringItemID,
        DailyFeatureOutcomeID,
        DailyFeatureOutcomeLabelID,
    ],
    ordinal: int,
    symbol: str,
    session: date,
    run_time: datetime,
    mode: OutcomeObservationMode,
    positive: bool,
    outcome_key: str,
    outcome_digest: str,
    path_digest: str,
) -> None:
    pipeline_id, scoring_id, _ = run_ids
    snapshot_id, pipeline_item_id, scoring_item_id, outcome_id, label_id = item_ids
    rows["feature_snapshots"].append(
        snapshot(snapshot_id, symbol, session, run_time, "READY", "[]")
    )
    rows["pipeline_items"].append(
        pipeline_item(
            pipeline_item_id, pipeline_id, snapshot_id, ordinal, symbol, session, run_time, "READY"
        )
    )
    rows["scoring_items"].append(
        scoring_item(
            scoring_item_id,
            scoring_id,
            pipeline_item_id,
            snapshot_id,
            ordinal,
            symbol,
            run_time,
            False,
        )
    )
    rows["outcomes"].append(
        outcome_row(
            outcome_id,
            outcome_key,
            outcome_digest,
            path_digest,
            pipeline_id,
            pipeline_item_id,
            scoring_id,
            scoring_item_id,
            snapshot_id,
            symbol,
            session,
            run_time,
            mode,
            positive,
        )
    )
    rows["labels"].append(
        label_row(
            label_id,
            outcome_id,
            pipeline_id,
            pipeline_item_id,
            scoring_id,
            scoring_item_id,
            snapshot_id,
            symbol,
            session,
            run_time,
            mode,
            positive,
            path_digest,
        )
    )


def snapshot(
    identifier: FeatureSnapshotID,
    symbol: str,
    session: date,
    run_time: datetime,
    quality: str,
    reasons: str,
) -> dict[str, object]:
    token = f"snapshot-{identifier.serialize()}"
    return {
        "feature_snapshot_id": identifier.value,
        "snapshot_key": f"feature-snapshot:v1:{_digest(token)}",
        "content_digest": _digest(f"{token}-content"),
        "symbol": symbol,
        "feature_set_code": "US_EQUITY_DAILY_TECHNICAL",
        "feature_set_version": "v1",
        "horizon_trading_days": 1,
        "as_of": run_time,
        "generated_at": run_time + timedelta(minutes=1),
        "latest_input_available_at": run_time,
        "quality_status": quality,
        "quality_reason_codes": reasons,
        "feature_values": '{"last_close":"100"}',
        "provenance": '[{"source":"synthetic"}]',
        "recorded_at": run_time + timedelta(minutes=1),
    }


def pipeline_item(
    identifier: DailyFeaturePipelineItemID,
    run_id: DailyFeaturePipelineRunID,
    snapshot_id: FeatureSnapshotID,
    ordinal: int,
    symbol: str,
    session: date,
    run_time: datetime,
    outcome: str,
) -> dict[str, object]:
    degraded = outcome == "DEGRADED"
    return {
        "daily_feature_pipeline_item_id": identifier.value,
        "daily_feature_pipeline_run_id": run_id.value,
        "ordinal": ordinal,
        "symbol": symbol,
        "mic_code": "XNGS",
        "completed_session_date": session,
        "outcome": outcome,
        "daily_bar_created_count": 0,
        "daily_bar_existing_count": 21,
        "feature_snapshot_id": snapshot_id.value,
        "feature_quality_status": "DEGRADED" if degraded else "READY",
        "safe_reason_code": "VOLUME_DATA_INCOMPLETE" if degraded else None,
        "provider_request_count": 0,
        "provider_credit_count": 0,
        "started_at": run_time + timedelta(minutes=2),
        "finished_at": run_time + timedelta(minutes=3),
        "recorded_at": run_time + timedelta(minutes=3),
    }


def scoring_item(
    identifier: DailyFeatureScoringItemID,
    run_id: DailyFeatureScoringRunID,
    pipeline_item_id: DailyFeaturePipelineItemID,
    snapshot_id: FeatureSnapshotID,
    ordinal: int,
    symbol: str,
    run_time: datetime,
    degraded: bool,
) -> dict[str, object]:
    values = {name: Decimal(ordinal * 10) for name in _SCORE_COLUMNS}
    if degraded:
        values["volume_score"] = None
    return {
        "daily_feature_scoring_item_id": identifier.value,
        "daily_feature_scoring_run_id": run_id.value,
        "source_daily_feature_pipeline_item_id": pipeline_item_id.value,
        "ordinal": ordinal,
        "rank": ordinal,
        "symbol": symbol,
        "mic_code": "XNGS",
        "feature_snapshot_id": snapshot_id.value,
        "source_quality_status": "DEGRADED" if degraded else "READY",
        "outcome": "SCORED_DEGRADED" if degraded else "SCORED_READY",
        **values,
        "safe_reason_code": None,
        "generated_at": run_time + timedelta(minutes=4),
        "recorded_at": run_time + timedelta(minutes=4),
    }


def pipeline_run(
    identifier: DailyFeaturePipelineRunID,
    universe_id: UniverseSnapshotID,
    index: int,
    session: date,
    run_time: datetime,
    total: int,
    ready: int,
    degraded: int,
) -> dict[str, object]:
    return {
        "daily_feature_pipeline_run_id": identifier.value,
        "run_key": f"daily-feature-run:v1:{_digest(f'pipeline-{index}')}",
        "content_digest": _digest(f"pipeline-content-{index}"),
        "universe_snapshot_id": universe_id.value,
        "pipeline_code": "US_EQUITY_DAILY_FEATURE_BATCH",
        "pipeline_version": "v1",
        "provider_code": SOURCE_PROVIDER_CODE,
        "calendar_code": CALENDAR_CODE,
        "calendar_version": CALENDAR_VERSION,
        "completed_session_date": session,
        "as_of": run_time,
        "completion_grace_seconds": 0,
        "adjustment_basis": "SPLIT_ADJUSTED",
        "feature_set_code": "US_EQUITY_DAILY_TECHNICAL",
        "feature_set_version": "v1",
        "horizon_trading_days": 1,
        "requested_session_count": 21,
        "status": "COMPLETED_WITH_WARNINGS" if degraded else "COMPLETED",
        "total_count": total,
        "ready_count": ready,
        "degraded_count": degraded,
        "data_insufficient_count": 0,
        "no_data_count": 0,
        "provider_error_count": 0,
        "calendar_error_count": 0,
        "not_attempted_count": 0,
        "estimated_credit_count": 0,
        "consumed_credit_count": 0,
        "started_at": run_time,
        "finished_at": run_time + timedelta(minutes=3),
        "recorded_at": run_time + timedelta(minutes=3),
    }


def scoring_run(
    identifier: DailyFeatureScoringRunID,
    pipeline_id: DailyFeaturePipelineRunID,
    index: int,
    run_time: datetime,
    total: int,
    ready: int,
    degraded: int,
) -> dict[str, object]:
    return {
        "daily_feature_scoring_run_id": identifier.value,
        "scoring_run_key": f"daily-feature-scoring-run:v1:{_digest(f'scoring-{index}')}",
        "content_digest": _digest(f"scoring-content-{index}"),
        "source_daily_feature_pipeline_run_id": pipeline_id.value,
        "scoring_policy_code": SCORING_POLICY_CODE,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "ranking_policy_code": RANKING_POLICY_CODE,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "status": "COMPLETED",
        "total_count": total,
        "scored_ready_count": ready,
        "scored_degraded_count": degraded,
        "unscorable_count": 0,
        "generated_at": run_time + timedelta(minutes=4),
        "recorded_at": run_time + timedelta(minutes=4),
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_SCORE_COLUMNS = (
    "momentum_score",
    "trend_score",
    "breakout_score",
    "price_action_score",
    "stability_score",
    "volume_score",
    "overall_relative_score",
)
