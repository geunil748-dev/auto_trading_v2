"""Canonical content digest for P4B.2A dataset snapshots."""

from auto_trading_v2.domain.calibration_datasets.models import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
)
from auto_trading_v2.domain.feature_outcomes import outcome_content_digest
from auto_trading_v2.domain.primitives import SessionDate, UtcTimestamp


def calibration_dataset_content_digest(
    dataset: ProbabilityCalibrationDataset,
    items: tuple[ProbabilityCalibrationDatasetItem, ...],
) -> str:
    payload = {
        "earliest_source_session_date": _date(dataset.earliest_source_session_date),
        "items": [_item_payload(item) for item in items],
        "latest_source_session_date": _date(dataset.latest_source_session_date),
        "not_positive_count": dataset.not_positive_count,
        "positive_count": dataset.positive_count,
        "prospective_count": dataset.prospective_count,
        "retrospective_replay_count": dataset.retrospective_replay_count,
        "status": dataset.status.value,
        "total_count": dataset.total_count,
        "unique_source_session_count": dataset.unique_source_session_count,
    }
    return outcome_content_digest(payload)


def _item_payload(item: ProbabilityCalibrationDatasetItem) -> dict[str, object]:
    return {
        "feature_snapshot_id": item.feature_snapshot_id.serialize(),
        "horizon_trading_days": item.horizon.value,
        "label_value": item.label_value.value,
        "mic_code": item.mic_code,
        "observation_mode": item.observation_mode.value,
        "ordinal": item.ordinal,
        "overall_relative_score": item.overall_relative_score.serialize(),
        "source_daily_feature_outcome_id": item.source_daily_feature_outcome_id.serialize(),
        "source_daily_feature_outcome_label_id": (
            item.source_daily_feature_outcome_label_id.serialize()
        ),
        "source_daily_feature_pipeline_item_id": (
            item.source_daily_feature_pipeline_item_id.serialize()
        ),
        "source_daily_feature_pipeline_run_id": (
            item.source_daily_feature_pipeline_run_id.serialize()
        ),
        "source_daily_feature_scoring_item_id": (
            item.source_daily_feature_scoring_item_id.serialize()
        ),
        "source_daily_feature_scoring_run_id": (
            item.source_daily_feature_scoring_run_id.serialize()
        ),
        "source_outcome_content_digest": item.source_outcome_content_digest,
        "source_outcome_key": item.source_outcome_key,
        "source_outcome_latest_input_available_at": UtcTimestamp(
            item.source_outcome_latest_input_available_at
        ).serialize(),
        "source_outcome_recorded_at": UtcTimestamp(item.source_outcome_recorded_at).serialize(),
        "source_path_revision_digest": item.source_path_revision_digest,
        "source_quality_status": item.source_quality_status.value,
        "source_rank": item.source_rank,
        "source_session_date": item.source_session_date.serialize(),
        "symbol": item.symbol.serialize(),
        "terminal_session_date": item.terminal_session_date.serialize(),
    }


def _date(value: SessionDate | None) -> str | None:
    return None if value is None else value.serialize()
