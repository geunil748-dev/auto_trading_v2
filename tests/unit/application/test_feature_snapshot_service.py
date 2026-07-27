from datetime import timedelta
from typing import cast

import pytest

from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    FeatureSnapshotCreationOutcome,
)
from auto_trading_v2.application.errors import PersistenceError
from auto_trading_v2.application.feature_snapshot_errors import (
    FeatureSnapshotConflictError,
    FeatureSnapshotRaceResolutionError,
)
from auto_trading_v2.application.services.feature_snapshot import (
    FeatureSnapshotCreationService,
)
from auto_trading_v2.domain.feature_snapshots import FeatureSnapshotValidationError
from tests.unit.application.feature_snapshot_fakes import (
    AS_OF,
    FakeFeatureSnapshotRepository,
    FakeUnitOfWork,
    FakeUnitOfWorkFactory,
    RecordingClock,
    RecordingIDFactory,
    command,
    stored_for,
)


def _service(
    *unit_of_works: FakeUnitOfWork,
    clock: RecordingClock | None = None,
) -> tuple[
    FeatureSnapshotCreationService,
    FakeUnitOfWorkFactory,
    RecordingClock,
    RecordingIDFactory,
]:
    factory = FakeUnitOfWorkFactory(list(unit_of_works))
    selected_clock = RecordingClock() if clock is None else clock
    identifier_factory = RecordingIDFactory()
    service = FeatureSnapshotCreationService(
        cast(object, factory),
        selected_clock,
        identifier_factory,
    )
    return service, factory, selected_clock, identifier_factory


def test_new_snapshot_is_created_with_one_clock_id_insert_and_commit() -> None:
    repository = FakeFeatureSnapshotRepository()
    unit_of_work = FakeUnitOfWork(repository)
    service, factory, clock, identifier_factory = _service(unit_of_work)

    result = service.create(command())

    assert result.outcome is FeatureSnapshotCreationOutcome.CREATED
    assert result.snapshot == repository.existing
    assert factory.calls == clock.calls == identifier_factory.calls == 1
    assert len(repository.add_calls) == 1
    assert unit_of_work.commit_calls == 1
    assert unit_of_work.rollback_calls == 0


def test_generated_at_equality_is_allowed_and_does_not_change_content_digest() -> None:
    first_uow = FakeUnitOfWork(FakeFeatureSnapshotRepository())
    first_service, _, _, _ = _service(first_uow, clock=RecordingClock(AS_OF))
    later_uow = FakeUnitOfWork(FakeFeatureSnapshotRepository())
    later_service, _, _, _ = _service(later_uow)

    first = first_service.create(command()).snapshot
    later = later_service.create(command()).snapshot

    assert first.generated_at == AS_OF
    assert first.snapshot_key == later.snapshot_key
    assert first.content_digest == later.content_digest


def test_exact_retry_returns_existing_without_id_write_or_commit() -> None:
    source = command()
    repository = FakeFeatureSnapshotRepository(stored_for(source))
    unit_of_work = FakeUnitOfWork(repository)
    service, _, clock, identifier_factory = _service(unit_of_work)

    result = service.create(source)

    assert result.outcome is FeatureSnapshotCreationOutcome.ALREADY_EXISTS
    assert clock.calls == 1
    assert identifier_factory.calls == 0
    assert repository.add_calls == []
    assert unit_of_work.commit_calls == 0


def test_same_key_with_different_digest_is_sanitized_conflict_without_write() -> None:
    requested = command({"close": 100, "secret_value": "do-not-leak"})
    existing = stored_for(command({"close": 101}))
    repository = FakeFeatureSnapshotRepository(existing)
    unit_of_work = FakeUnitOfWork(repository)
    service, _, _, identifier_factory = _service(unit_of_work)

    with pytest.raises(FeatureSnapshotConflictError) as captured:
        service.create(requested)

    rendered = f"{captured.value!s} {captured.value!r}"
    assert "do-not-leak" not in rendered
    assert "secret_value" not in rendered
    assert identifier_factory.calls == 0
    assert repository.add_calls == []
    assert unit_of_work.commit_calls == 0


def test_unique_race_rechecks_and_returns_exact_existing_without_commit() -> None:
    source = command()
    first = FakeUnitOfWork(FakeFeatureSnapshotRepository(duplicate_on_add=True))
    second = FakeUnitOfWork(FakeFeatureSnapshotRepository(stored_for(source)))
    service, factory, clock, identifier_factory = _service(first, second)

    result = service.create(source)

    assert result.outcome is FeatureSnapshotCreationOutcome.ALREADY_EXISTS
    assert factory.calls == 2
    assert clock.calls == identifier_factory.calls == 1
    assert first.rollback_calls == 1
    assert first.commit_calls == second.commit_calls == 0


def test_unique_race_with_different_content_becomes_conflict() -> None:
    requested = command({"close": 100})
    first = FakeUnitOfWork(FakeFeatureSnapshotRepository(duplicate_on_add=True))
    second = FakeUnitOfWork(FakeFeatureSnapshotRepository(stored_for(command({"close": 999}))))
    service, _, _, _ = _service(first, second)

    with pytest.raises(FeatureSnapshotConflictError):
        service.create(requested)

    assert first.commit_calls == second.commit_calls == 0


def test_unique_race_without_visible_row_is_safe_resolution_error() -> None:
    first = FakeUnitOfWork(FakeFeatureSnapshotRepository(duplicate_on_add=True))
    second = FakeUnitOfWork(FakeFeatureSnapshotRepository())
    service, _, _, _ = _service(first, second)

    with pytest.raises(FeatureSnapshotRaceResolutionError):
        service.create(command())


def test_invalid_command_and_generated_before_cutoff_have_no_write_or_commit() -> None:
    unit_of_work = FakeUnitOfWork(FakeFeatureSnapshotRepository())
    service, factory, clock, identifier_factory = _service(unit_of_work)

    with pytest.raises(FeatureSnapshotValidationError):
        service.create(cast(CreateFeatureSnapshotCommand, object()))

    assert factory.calls == clock.calls == identifier_factory.calls == 0
    early_clock = RecordingClock(AS_OF - timedelta(microseconds=1))
    early_service, early_factory, _, early_id_factory = _service(
        FakeUnitOfWork(FakeFeatureSnapshotRepository()),
        clock=early_clock,
    )
    with pytest.raises(FeatureSnapshotValidationError):
        early_service.create(command())
    assert early_factory.calls == early_id_factory.calls == 0
    assert early_clock.calls == 1


@pytest.mark.parametrize("failure_point", ["get", "add"])
def test_repository_error_rolls_back_and_remains_payload_safe(failure_point: str) -> None:
    repository = FakeFeatureSnapshotRepository(
        error_on_get=failure_point == "get",
        error_on_add=failure_point == "add",
    )
    unit_of_work = FakeUnitOfWork(repository)
    service, _, _, _ = _service(unit_of_work)

    with pytest.raises(PersistenceError) as captured:
        service.create(command({"secret_value": "do-not-leak"}))

    assert "do-not-leak" not in str(captured.value)
    assert unit_of_work.rollback_calls == 1
    assert unit_of_work.commit_calls == 0
