from dataclasses import dataclass, replace
from uuid import UUID

import pytest

from auto_trading_v2.application.services.probability_calibration_dataset_builder import (
    build_calibration_dataset,
    validate_and_order_sources,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetStatus,
    ProbabilityCalibrationDatasetValidationError,
)
from auto_trading_v2.domain.feature_outcomes import OutcomeObservationMode
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import (
    ProbabilityCalibrationDatasetID,
    ProbabilityCalibrationDatasetItemID,
)
from tests.unit.p4b2a_helpers import (
    GENERATED_AT,
    dataset_identity,
    make_label,
    make_outcomes,
    make_source,
)


@dataclass
class DatasetIDs:
    value: int = 50_000
    calls: int = 0

    def new(self) -> ProbabilityCalibrationDatasetID:
        self.calls += 1
        return ProbabilityCalibrationDatasetID(UUID(int=self.value + self.calls))


@dataclass
class ItemIDs:
    value: int = 60_000
    calls: int = 0

    def new(self) -> ProbabilityCalibrationDatasetItemID:
        self.calls += 1
        return ProbabilityCalibrationDatasetItemID(UUID(int=self.value + self.calls))


def test_empty_dataset_is_a_valid_immutable_snapshot() -> None:
    aggregate = build_calibration_dataset(
        dataset_identity(), (), (), GENERATED_AT, DatasetIDs(), ItemIDs()
    )

    assert aggregate.dataset.status is ProbabilityCalibrationDatasetStatus.EMPTY
    assert aggregate.dataset.total_count == 0
    assert aggregate.dataset.earliest_source_session_date is None
    assert aggregate.items == ()


def test_mixed_dataset_is_order_independent_and_preserves_mode_counts() -> None:
    outcomes = make_outcomes((("MSFT", "95"), ("AAPL", "105")))
    labels = (
        make_label(outcomes[0], identifier=41_001),
        make_label(outcomes[1], identifier=41_002),
    )
    sources = (make_source(outcomes[0], rank=2), make_source(outcomes[1], rank=1))
    replay_source = replace(
        sources[0], observation_mode=OutcomeObservationMode.RETROSPECTIVE_REPLAY
    )
    replay_label = replace(labels[0], observation_mode=OutcomeObservationMode.RETROSPECTIVE_REPLAY)

    ordered_sources = validate_and_order_sources((replay_source, sources[1]), dataset_identity())
    label_by_outcome = {
        replay_label.source_daily_feature_outcome_id: replay_label,
        labels[1].source_daily_feature_outcome_id: labels[1],
    }
    ordered_labels = tuple(
        label_by_outcome[source.source_daily_feature_outcome_id] for source in ordered_sources
    )
    first = build_calibration_dataset(
        dataset_identity(), ordered_sources, ordered_labels, GENERATED_AT, DatasetIDs(), ItemIDs()
    )
    second_sources = validate_and_order_sources(
        tuple(reversed(ordered_sources)), dataset_identity()
    )
    second_labels = tuple(
        label_by_outcome[source.source_daily_feature_outcome_id] for source in second_sources
    )
    second = build_calibration_dataset(
        dataset_identity(),
        second_sources,
        second_labels,
        GENERATED_AT,
        DatasetIDs(70_000),
        ItemIDs(80_000),
    )

    assert [item.ordinal for item in first.items] == [1, 2]
    assert [item.source_rank for item in first.items] == [1, 2]
    assert (first.dataset.positive_count, first.dataset.not_positive_count) == (1, 1)
    assert (first.dataset.prospective_count, first.dataset.retrospective_replay_count) == (1, 1)
    assert first.dataset.content_digest == second.dataset.content_digest


def test_degraded_or_duplicate_scoring_source_is_rejected() -> None:
    outcomes = make_outcomes((("AAPL", "105"), ("MSFT", "95")))
    ready = make_source(outcomes[0])
    degraded = make_source(outcomes[1], quality=FeatureQualityStatus.DEGRADED)

    with pytest.raises(
        ProbabilityCalibrationDatasetValidationError,
        match="DATASET_SOURCE_CONTRACT_INVALID",
    ):
        validate_and_order_sources((degraded,), dataset_identity())
    with pytest.raises(
        ProbabilityCalibrationDatasetValidationError,
        match="DATASET_SOURCE_REVISION_DUPLICATE",
    ):
        validate_and_order_sources((ready, ready), dataset_identity())

    late = replace(ready, outcome_recorded_at=GENERATED_AT)
    with pytest.raises(
        ProbabilityCalibrationDatasetValidationError,
        match="DATASET_SOURCE_CONTRACT_INVALID",
    ):
        validate_and_order_sources((late,), dataset_identity())


def test_label_and_source_chain_must_match_exactly() -> None:
    outcome = make_outcomes((("AAPL", "105"),))[0]
    source = make_source(outcome)
    label = make_label(outcome)
    mismatched = replace(label, mic_code="XNYS")

    with pytest.raises(
        ProbabilityCalibrationDatasetValidationError,
        match="DATASET_LABEL_SOURCE_MISMATCH",
    ):
        build_calibration_dataset(
            dataset_identity(),
            (source,),
            (mismatched,),
            GENERATED_AT,
            DatasetIDs(),
            ItemIDs(),
        )
