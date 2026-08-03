from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal

from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    SOURCE_PROVIDER_CODE,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabelIdentity,
    fixed_label_policy_values,
    outcome_label_key,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
)


def outcome_row(
    identifier: DailyFeatureOutcomeID,
    key: str,
    content: str,
    path: str,
    pipeline_id: DailyFeaturePipelineRunID,
    pipeline_item_id: DailyFeaturePipelineItemID,
    scoring_id: DailyFeatureScoringRunID,
    scoring_item_id: DailyFeatureScoringItemID,
    snapshot_id: FeatureSnapshotID,
    symbol: str,
    session: date,
    run_time: datetime,
    mode: OutcomeObservationMode,
    positive: bool,
) -> dict[str, object]:
    observed = run_time + timedelta(minutes=5)
    return {
        "daily_feature_outcome_id": identifier.value,
        "outcome_key": key,
        "content_digest": content,
        "path_revision_digest": path,
        "source_daily_feature_scoring_run_id": scoring_id.value,
        "source_daily_feature_scoring_item_id": scoring_item_id.value,
        "source_daily_feature_pipeline_run_id": pipeline_id.value,
        "source_daily_feature_pipeline_item_id": pipeline_item_id.value,
        "feature_snapshot_id": snapshot_id.value,
        "symbol": symbol,
        "mic_code": "XNGS",
        "provider_code": SOURCE_PROVIDER_CODE,
        "calendar_code": CALENDAR_CODE,
        "calendar_version": CALENDAR_VERSION,
        "source_session_date": session,
        "terminal_session_date": session + timedelta(days=3),
        "horizon_trading_days": 1,
        "outcome_policy_code": OUTCOME_POLICY_CODE,
        "outcome_policy_version": OUTCOME_POLICY_VERSION,
        "observation_as_of": observed,
        "reference_close": Decimal("100"),
        "terminal_close": Decimal("101") if positive else Decimal("99"),
        "forward_close_return": Decimal("0.01") if positive else Decimal("-0.01"),
        "maximum_favorable_excursion_rate": Decimal("0.02"),
        "maximum_adverse_excursion_rate": Decimal("-0.02"),
        "future_bar_count": 1,
        "future_bar_provenance": "[]",
        "latest_input_available_at": observed,
        "observation_mode": mode.value,
        "generated_at": observed,
        "recorded_at": observed,
    }


def label_row(
    identifier: DailyFeatureOutcomeLabelID,
    outcome_id: DailyFeatureOutcomeID,
    pipeline_id: DailyFeaturePipelineRunID,
    pipeline_item_id: DailyFeaturePipelineItemID,
    scoring_id: DailyFeatureScoringRunID,
    scoring_item_id: DailyFeatureScoringItemID,
    snapshot_id: FeatureSnapshotID,
    symbol: str,
    session: date,
    run_time: datetime,
    mode: OutcomeObservationMode,
    positive: bool,
    path_digest: str,
) -> dict[str, object]:
    code, version = fixed_label_policy_values()
    generated = run_time + timedelta(minutes=6)
    identity = DailyFeatureOutcomeLabelIdentity(outcome_id, code, version)
    return {
        "daily_feature_outcome_label_id": identifier.value,
        "label_key": outcome_label_key(identity),
        "content_digest": _digest(f"label-{identifier.serialize()}"),
        "source_daily_feature_outcome_id": outcome_id.value,
        "source_daily_feature_scoring_run_id": scoring_id.value,
        "source_daily_feature_scoring_item_id": scoring_item_id.value,
        "source_daily_feature_pipeline_run_id": pipeline_id.value,
        "source_daily_feature_pipeline_item_id": pipeline_item_id.value,
        "feature_snapshot_id": snapshot_id.value,
        "symbol": symbol,
        "mic_code": "XNGS",
        "horizon_trading_days": 1,
        "source_session_date": session,
        "terminal_session_date": session + timedelta(days=3),
        "observation_mode": mode.value,
        "source_path_revision_digest": path_digest,
        "label_policy_code": code.value,
        "label_policy_version": version.value,
        "label_value": "POSITIVE" if positive else "NOT_POSITIVE",
        "source_latest_input_available_at": run_time + timedelta(minutes=5),
        "generated_at": generated,
        "recorded_at": generated,
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
