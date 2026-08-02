from datetime import UTC, datetime

import pytest

from auto_trading_v2.application.calibration_dataset_errors import (
    ProbabilityCalibrationDatasetConflictError,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    CreateProbabilityCalibrationDatasetCommand,
    ProbabilityCalibrationDatasetCreationOutcome,
)
from auto_trading_v2.application.services.probability_calibration_dataset import (
    ProbabilityCalibrationDatasetCreationService,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetValidationError,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from tests.unit.application.p4b2a_fakes import (
    CountingClock,
    DatasetIDs,
    FakeDatasetRepository,
    FakeLabelCreationService,
    FakeOutcomeRepository,
    FakeSourceReader,
    FakeUnitOfWorkFactory,
    ItemIDs,
)
from tests.unit.p4b2a_helpers import (
    DATASET_AS_OF,
    GENERATED_AT,
    make_label,
    make_outcomes,
    make_source,
)


def _context() -> tuple[
    ProbabilityCalibrationDatasetCreationService,
    FakeUnitOfWorkFactory,
    FakeSourceReader,
    FakeLabelCreationService,
    CountingClock,
    DatasetIDs,
    ItemIDs,
]:
    outcomes = make_outcomes((("MSFT", "95"), ("AAPL", "105")))
    sources = (make_source(outcomes[0], rank=2), make_source(outcomes[1], rank=1))
    labels = {
        outcome.daily_feature_outcome_id: make_label(outcome, identifier=93_000 + index)
        for index, outcome in enumerate(outcomes, 1)
    }
    factory = FakeUnitOfWorkFactory(FakeOutcomeRepository({}))
    reader = FakeSourceReader(sources)
    label_service = FakeLabelCreationService(labels)
    clock = CountingClock(GENERATED_AT)
    dataset_ids = DatasetIDs()
    item_ids = ItemIDs()
    service = ProbabilityCalibrationDatasetCreationService(
        factory,  # type: ignore[arg-type]
        reader,
        label_service,  # type: ignore[arg-type]
        clock,
        dataset_ids,
        item_ids,
    )
    return service, factory, reader, label_service, clock, dataset_ids, item_ids


def _command(*, as_of: datetime = DATASET_AS_OF) -> CreateProbabilityCalibrationDatasetCommand:
    return CreateProbabilityCalibrationDatasetCommand(TradingDayHorizon(1), as_of)


def test_create_is_one_dataset_transaction_and_retry_skips_all_dataset_work() -> None:
    service, factory, reader, labels, clock, dataset_ids, item_ids = _context()

    created = service.create(_command())
    counters = (
        reader.calls,
        labels.calls,
        dataset_ids.calls,
        item_ids.calls,
        factory.datasets.inserts,
        factory.commits,
    )
    retried = service.create(_command())

    assert created.outcome is ProbabilityCalibrationDatasetCreationOutcome.CREATED
    assert created.dataset.dataset.total_count == 2
    assert [item.source_rank for item in created.dataset.items] == [1, 2]
    assert retried.outcome is ProbabilityCalibrationDatasetCreationOutcome.ALREADY_EXISTS
    assert retried.dataset == created.dataset
    assert counters == (1, 2, 1, 2, 1, 1)
    assert (
        reader.calls,
        labels.calls,
        dataset_ids.calls,
        item_ids.calls,
        factory.datasets.inserts,
        factory.commits,
    ) == counters
    assert clock.calls == 2


def test_future_dataset_as_of_is_rejected_before_any_read_or_write() -> None:
    service, factory, reader, labels, clock, dataset_ids, item_ids = _context()

    with pytest.raises(
        ProbabilityCalibrationDatasetValidationError,
        match="DATASET_AS_OF_IN_FUTURE",
    ):
        service.create(_command(as_of=datetime(2027, 1, 1, tzinfo=UTC)))

    assert clock.calls == 1
    assert (reader.calls, labels.calls, dataset_ids.calls, item_ids.calls) == (0, 0, 0, 0)
    assert (factory.datasets.key_reads, factory.datasets.inserts, factory.commits) == (0, 0, 0)


@pytest.mark.parametrize("conflict", [False, True])
def test_dataset_unique_race_reloads_aggregate_or_reports_safe_conflict(conflict: bool) -> None:
    service, factory, _, _, _, _, _ = _context()
    factory.datasets = FakeDatasetRepository(duplicate_once=True, conflict_winner=conflict)

    if conflict:
        with pytest.raises(ProbabilityCalibrationDatasetConflictError) as captured:
            service.create(_command())
        assert "AAPL" not in str(captured.value)
    else:
        result = service.create(_command())
        assert result.outcome is ProbabilityCalibrationDatasetCreationOutcome.ALREADY_EXISTS

    assert factory.rollbacks == 1
    assert factory.commits == 0
