"""Pure validation and aggregate construction for P4B.2A datasets."""

import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
)
from auto_trading_v2.application.ports.id_factory import (
    ProbabilityCalibrationDatasetIDFactory,
    ProbabilityCalibrationDatasetItemIDFactory,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetIdentity,
    ProbabilityCalibrationDatasetItem,
    ProbabilityCalibrationDatasetStatus,
    ProbabilityCalibrationDatasetValidationError,
    ProbabilityCalibrationDatasetWithItems,
    calibration_dataset_content_digest,
    calibration_dataset_key,
)
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    SOURCE_PROVIDER_CODE,
    ForwardReturn,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.feature_scoring import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
    RelativeScore,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabel,
    positive_forward_close_label,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    ProbabilityCalibrationDatasetID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_OUTCOME_KEY = re.compile(r"^daily-feature-outcome:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})


def validate_and_order_sources(
    sources: Sequence[CalibrationDatasetSourceRecord],
    identity: ProbabilityCalibrationDatasetIdentity,
) -> tuple[CalibrationDatasetSourceRecord, ...]:
    for source in sources:
        _validate_source(source, identity)
    ordered = tuple(sorted(sources, key=_source_order_key))
    source_items = [source.source_daily_feature_scoring_item_id for source in ordered]
    if len(source_items) != len(set(source_items)):
        _invalid("DATASET_SOURCE_REVISION_DUPLICATE")
    return ordered


def build_calibration_dataset(
    identity: ProbabilityCalibrationDatasetIdentity,
    sources: tuple[CalibrationDatasetSourceRecord, ...],
    labels: tuple[DailyFeatureOutcomeLabel, ...],
    generated_at: datetime,
    dataset_id_factory: ProbabilityCalibrationDatasetIDFactory,
    item_id_factory: ProbabilityCalibrationDatasetItemIDFactory,
) -> ProbabilityCalibrationDatasetWithItems:
    if len(sources) != len(labels):
        _invalid("DATASET_LABEL_COUNT_MISMATCH")
    dataset_id = dataset_id_factory.new()
    items = tuple(
        _item(dataset_id, ordinal, source, label, generated_at, item_id_factory)
        for ordinal, (source, label) in enumerate(zip(sources, labels, strict=True), 1)
    )
    status = (
        ProbabilityCalibrationDatasetStatus.EMPTY
        if not items
        else ProbabilityCalibrationDatasetStatus.READY
    )
    positive_count = sum(label.label_value.value == "POSITIVE" for label in labels)
    prospective_count = sum(source.observation_mode.value == "PROSPECTIVE" for source in sources)
    sessions = sorted(
        {source.source_session_date for source in sources}, key=lambda value: value.value
    )
    provisional = ProbabilityCalibrationDataset(
        probability_calibration_dataset_id=dataset_id,
        dataset_key=calibration_dataset_key(identity),
        content_digest="0" * 64,
        identity=identity,
        status=status,
        total_count=len(items),
        positive_count=positive_count,
        not_positive_count=len(items) - positive_count,
        prospective_count=prospective_count,
        retrospective_replay_count=len(items) - prospective_count,
        unique_source_session_count=len(sessions),
        earliest_source_session_date=None if not sessions else sessions[0],
        latest_source_session_date=None if not sessions else sessions[-1],
        generated_at=generated_at,
        recorded_at=generated_at,
    )
    digest = calibration_dataset_content_digest(provisional, items)
    dataset = replace(provisional, content_digest=digest)
    return ProbabilityCalibrationDatasetWithItems(dataset, items)


def _item(
    dataset_id: ProbabilityCalibrationDatasetID,
    ordinal: int,
    source: CalibrationDatasetSourceRecord,
    label: DailyFeatureOutcomeLabel,
    generated_at: datetime,
    item_id_factory: ProbabilityCalibrationDatasetItemIDFactory,
) -> ProbabilityCalibrationDatasetItem:
    if (
        label.source_daily_feature_outcome_id != source.source_daily_feature_outcome_id
        or label.source_daily_feature_scoring_run_id != source.source_daily_feature_scoring_run_id
        or label.source_daily_feature_scoring_item_id != source.source_daily_feature_scoring_item_id
        or label.source_daily_feature_pipeline_run_id != source.source_daily_feature_pipeline_run_id
        or label.source_daily_feature_pipeline_item_id
        != source.source_daily_feature_pipeline_item_id
        or label.feature_snapshot_id != source.feature_snapshot_id
        or label.symbol != source.symbol
        or label.mic_code != source.mic_code
        or label.horizon != source.horizon
        or label.source_session_date != source.source_session_date
        or label.terminal_session_date != source.terminal_session_date
        or label.observation_mode != source.observation_mode
        or label.source_path_revision_digest != source.source_path_revision_digest
        or label.source_latest_input_available_at != source.outcome_latest_input_available_at
        or label.label_value != positive_forward_close_label(source.forward_close_return)
    ):
        _invalid("DATASET_LABEL_SOURCE_MISMATCH")
    return ProbabilityCalibrationDatasetItem(
        probability_calibration_dataset_item_id=item_id_factory.new(),
        probability_calibration_dataset_id=dataset_id,
        ordinal=ordinal,
        source_daily_feature_outcome_label_id=label.daily_feature_outcome_label_id,
        source_daily_feature_outcome_id=source.source_daily_feature_outcome_id,
        source_daily_feature_scoring_run_id=source.source_daily_feature_scoring_run_id,
        source_daily_feature_scoring_item_id=source.source_daily_feature_scoring_item_id,
        source_daily_feature_pipeline_run_id=source.source_daily_feature_pipeline_run_id,
        source_daily_feature_pipeline_item_id=source.source_daily_feature_pipeline_item_id,
        feature_snapshot_id=source.feature_snapshot_id,
        source_outcome_key=source.source_outcome_key,
        source_outcome_content_digest=source.source_outcome_content_digest,
        symbol=source.symbol,
        mic_code=source.mic_code,
        horizon=source.horizon,
        source_session_date=source.source_session_date,
        terminal_session_date=source.terminal_session_date,
        observation_mode=source.observation_mode,
        source_quality_status=source.source_quality_status,
        overall_relative_score=source.overall_relative_score,
        source_rank=source.rank,
        label_value=label.label_value,
        source_path_revision_digest=source.source_path_revision_digest,
        source_outcome_latest_input_available_at=source.outcome_latest_input_available_at,
        source_outcome_recorded_at=source.outcome_recorded_at,
        generated_at=generated_at,
        recorded_at=generated_at,
    )


def _validate_source(
    source: CalibrationDatasetSourceRecord,
    identity: ProbabilityCalibrationDatasetIdentity,
) -> None:
    types = (
        (source.source_daily_feature_scoring_run_id, DailyFeatureScoringRunID),
        (source.source_daily_feature_scoring_item_id, DailyFeatureScoringItemID),
        (source.source_daily_feature_pipeline_run_id, DailyFeaturePipelineRunID),
        (source.source_daily_feature_pipeline_item_id, DailyFeaturePipelineItemID),
        (source.feature_snapshot_id, FeatureSnapshotID),
        (source.source_daily_feature_outcome_id, DailyFeatureOutcomeID),
        (source.symbol, Symbol),
        (source.horizon, TradingDayHorizon),
        (source.source_session_date, SessionDate),
        (source.terminal_session_date, SessionDate),
        (source.observation_mode, OutcomeObservationMode),
        (source.source_quality_status, FeatureQualityStatus),
        (source.overall_relative_score, RelativeScore),
        (source.forward_close_return, ForwardReturn),
    )
    if any(not isinstance(value, expected_type) for value, expected_type in types):
        _invalid("DATASET_SOURCE_CONTRACT_INVALID")
    timestamps = (
        source.source_scoring_generated_at,
        source.source_scoring_item_recorded_at,
        source.outcome_latest_input_available_at,
        source.outcome_recorded_at,
    )
    try:
        scoring_generated, scoring_recorded, outcome_available, outcome_recorded = (
            normalize_utc(value) for value in timestamps
        )
    except (TypeError, ValueError):
        _invalid("DATASET_SOURCE_CONTRACT_INVALID")
    expected = (
        SOURCE_PROVIDER_CODE,
        CALENDAR_CODE,
        CALENDAR_VERSION,
        OUTCOME_POLICY_CODE,
        OUTCOME_POLICY_VERSION,
        SCORING_POLICY_CODE,
        SCORING_POLICY_VERSION,
        RANKING_POLICY_CODE,
        RANKING_POLICY_VERSION,
    )
    actual = (
        source.provider_code,
        source.calendar_code,
        source.calendar_version,
        source.outcome_policy_code,
        source.outcome_policy_version,
        source.scoring_policy_code,
        source.scoring_policy_version,
        source.ranking_policy_code,
        source.ranking_policy_version,
    )
    cutoff = identity.dataset_as_of
    if (
        actual != expected
        or source.horizon != identity.horizon
        or source.source_quality_status is not FeatureQualityStatus.READY
        or isinstance(source.rank, bool)
        or not isinstance(source.rank, int)
        or not 1 <= source.rank <= 100
        or source.mic_code not in _MICS
        or source.source_session_date.value >= source.terminal_session_date.value
        or not _OUTCOME_KEY.fullmatch(source.source_outcome_key)
        or not _DIGEST.fullmatch(source.source_outcome_content_digest)
        or not _DIGEST.fullmatch(source.source_path_revision_digest)
        or scoring_generated > scoring_recorded
        or outcome_available > outcome_recorded
        or scoring_generated > cutoff
        or scoring_recorded > cutoff
        or outcome_available > cutoff
        or outcome_recorded > cutoff
    ):
        _invalid("DATASET_SOURCE_CONTRACT_INVALID")


def _source_order_key(source: CalibrationDatasetSourceRecord) -> tuple[object, ...]:
    return (
        source.source_session_date.value,
        source.source_daily_feature_scoring_run_id.serialize(),
        source.rank,
        source.mic_code,
        source.symbol.serialize(),
        source.source_daily_feature_outcome_id.serialize(),
    )


def _invalid(category: str) -> None:
    raise ProbabilityCalibrationDatasetValidationError(category)
