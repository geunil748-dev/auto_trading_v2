from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_outcome_labels,
    daily_feature_outcomes,
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
    feature_snapshots,
    universe_snapshots,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
)
from auto_trading_v2.application.services.probability_calibration_dataset_builder import (
    build_calibration_dataset,
    validate_and_order_sources,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetIdentity,
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabel,
    DailyFeatureOutcomeLabelIdentity,
    PositiveForwardCloseLabel,
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
    ProbabilityCalibrationDatasetID,
    ProbabilityCalibrationDatasetItemID,
    UniverseSnapshotID,
)
from tests.integration.training_readiness.synthetic_rows import pipeline_run, scoring_run

SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "META")
GENERATED_AT = datetime(2026, 8, 3, 1, tzinfo=UTC)


@dataclass
class DatasetIDs:
    next_value: int

    def new(self) -> ProbabilityCalibrationDatasetID:
        self.next_value += 1
        return ProbabilityCalibrationDatasetID(UUID(int=self.next_value))


@dataclass
class ItemIDs:
    next_value: int

    def new(self) -> ProbabilityCalibrationDatasetItemID:
        self.next_value += 1
        return ProbabilityCalibrationDatasetItemID(UUID(int=self.next_value))


def append_universe_and_runs(
    rows: dict[str, list[dict[str, object]]],
    ids: tuple[DailyFeaturePipelineRunID, DailyFeatureScoringRunID, UniverseSnapshotID],
    index: int,
    session: date,
    run_time: datetime,
    total: int,
    ready: int,
    degraded: int,
) -> None:
    pipeline_id, scoring_id, universe_id = ids
    rows["universes"].append(
        {
            "universe_snapshot_id": universe_id.value,
            "universe_key": f"universe:v1:{_digest(f'universe-{index}')}",
            "content_digest": _digest(f"universe-content-{index}"),
            "universe_code": f"READINESS_{index}",
            "universe_version": "v1",
            "member_count": total,
            "members": json.dumps(SYMBOLS[:total]),
            "generated_at": run_time,
            "recorded_at": run_time,
        }
    )
    rows["pipeline_runs"].append(
        pipeline_run(pipeline_id, universe_id, index, session, run_time, total, ready, degraded)
    )
    rows["scoring_runs"].append(
        scoring_run(scoring_id, pipeline_id, index, run_time, total, ready, degraded)
    )


def aggregate_dataset(
    identity: ProbabilityCalibrationDatasetIdentity,
    source_values: tuple[CalibrationDatasetSourceRecord, ...],
    labels: dict[DailyFeatureOutcomeID, DailyFeatureOutcomeLabel],
    seed: int,
) -> ProbabilityCalibrationDatasetWithItems:
    ordered = validate_and_order_sources(source_values, identity)
    ordered_labels = tuple(labels[source.source_daily_feature_outcome_id] for source in ordered)
    return build_calibration_dataset(
        identity,
        ordered,
        ordered_labels,
        GENERATED_AT,
        DatasetIDs(seed),
        ItemIDs(seed + 10_000),
    )


def label(
    source: CalibrationDatasetSourceRecord,
    identifier: DailyFeatureOutcomeLabelID,
    value: PositiveForwardCloseLabel,
    run_time: datetime,
) -> DailyFeatureOutcomeLabel:
    code, version = fixed_label_policy_values()
    identity = DailyFeatureOutcomeLabelIdentity(
        source.source_daily_feature_outcome_id, code, version
    )
    generated = run_time + timedelta(minutes=6)
    return DailyFeatureOutcomeLabel(
        identifier,
        outcome_label_key(identity),
        _digest(f"label-{identifier.serialize()}"),
        source.source_daily_feature_outcome_id,
        source.source_daily_feature_scoring_run_id,
        source.source_daily_feature_scoring_item_id,
        source.source_daily_feature_pipeline_run_id,
        source.source_daily_feature_pipeline_item_id,
        source.feature_snapshot_id,
        source.symbol,
        source.mic_code,
        source.horizon,
        source.source_session_date,
        source.terminal_session_date,
        source.observation_mode,
        source.source_path_revision_digest,
        code,
        version,
        value,
        source.outcome_latest_input_available_at,
        generated,
        generated,
    )


def run_ids(
    index: int,
) -> tuple[DailyFeaturePipelineRunID, DailyFeatureScoringRunID, UniverseSnapshotID]:
    base = 100_000 + index * 10
    return (
        DailyFeaturePipelineRunID(UUID(int=base + 1)),
        DailyFeatureScoringRunID(UUID(int=base + 2)),
        UniverseSnapshotID(UUID(int=base + 3)),
    )


def item_ids(
    index: int,
) -> tuple[
    FeatureSnapshotID,
    DailyFeaturePipelineItemID,
    DailyFeatureScoringItemID,
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
]:
    base = 200_000 + index * 10
    return (
        FeatureSnapshotID(UUID(int=base + 1)),
        DailyFeaturePipelineItemID(UUID(int=base + 2)),
        DailyFeatureScoringItemID(UUID(int=base + 3)),
        DailyFeatureOutcomeID(UUID(int=base + 4)),
        DailyFeatureOutcomeLabelID(UUID(int=base + 5)),
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


TABLE_ORDER = {
    "universes": universe_snapshots,
    "feature_snapshots": feature_snapshots,
    "pipeline_runs": daily_feature_pipeline_runs,
    "pipeline_items": daily_feature_pipeline_items,
    "scoring_runs": daily_feature_scoring_runs,
    "scoring_items": daily_feature_scoring_items,
    "outcomes": daily_feature_outcomes,
    "labels": daily_feature_outcome_labels,
}
