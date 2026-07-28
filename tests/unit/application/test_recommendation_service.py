from dataclasses import replace
from datetime import timedelta
from typing import cast

import pytest

from auto_trading_v2.application.contracts.recommendations import (
    CreateRecommendationCommand,
    RecommendationCreationOutcome,
)
from auto_trading_v2.application.errors import PersistenceError
from auto_trading_v2.application.recommendation_errors import (
    RecommendationConflictError,
    RecommendationRaceResolutionError,
    RecommendationSourceNotFoundError,
    RecommendationSourceRejectedError,
)
from auto_trading_v2.application.services import RecommendationCreationService
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.recommendations import (
    RecommendationDisposition,
    RecommendationValidationError,
)
from tests.unit.application.recommendation_fakes import (
    GENERATED_AT,
    FakeRecommendationRepository,
    FakeUnitOfWork,
    FakeUnitOfWorkFactory,
    RecordingClock,
    RecordingIDFactory,
    command,
    feature_snapshot,
    stored_recommendation,
)
from tests.unit.domain.recommendations.helpers import plan


def _service(
    *unit_of_works: FakeUnitOfWork,
    clock: RecordingClock | None = None,
) -> tuple[
    RecommendationCreationService,
    FakeUnitOfWorkFactory,
    RecordingClock,
    RecordingIDFactory,
]:
    factory = FakeUnitOfWorkFactory(list(unit_of_works))
    selected_clock = RecordingClock() if clock is None else clock
    identifier_factory = RecordingIDFactory()
    return (
        RecommendationCreationService(
            cast(object, factory),
            selected_clock,
            identifier_factory,
        ),
        factory,
        selected_clock,
        identifier_factory,
    )


def test_created_uses_one_clock_id_insert_and_commit_in_one_uow() -> None:
    repository = FakeRecommendationRepository()
    unit_of_work = FakeUnitOfWork(feature_snapshot(), repository)
    service, factory, clock, identifier_factory = _service(unit_of_work)

    result = service.create(command())

    assert result.outcome is RecommendationCreationOutcome.CREATED
    assert result.recommendation == repository.existing
    assert factory.calls == clock.calls == identifier_factory.calls == 1
    assert len(repository.add_calls) == 1
    assert unit_of_work.feature_snapshots.calls == 1
    assert unit_of_work.commit_calls == 1
    assert unit_of_work.rollback_calls == 0


def test_exact_retry_has_no_id_insert_or_commit() -> None:
    source_command = command()
    repository = FakeRecommendationRepository(stored_recommendation(source_command))
    unit_of_work = FakeUnitOfWork(feature_snapshot(), repository)
    service, _, clock, identifier_factory = _service(unit_of_work)

    result = service.create(source_command)

    assert result.outcome is RecommendationCreationOutcome.ALREADY_EXISTS
    assert clock.calls == 1
    assert identifier_factory.calls == 0
    assert repository.add_calls == []
    assert unit_of_work.commit_calls == 0


def test_same_identity_different_content_is_sanitized_conflict() -> None:
    requested = command(reason_codes=("DO_NOT_LEAK_SECRET",))
    existing = stored_recommendation(command(reason_codes=("OTHER_REASON",)))
    repository = FakeRecommendationRepository(existing)
    unit_of_work = FakeUnitOfWork(feature_snapshot(), repository)
    service, _, _, identifier_factory = _service(unit_of_work)

    with pytest.raises(RecommendationConflictError) as captured:
        service.create(requested)

    rendered = f"{captured.value!s} {captured.value!r}"
    assert "DO_NOT_LEAK_SECRET" not in rendered
    assert identifier_factory.calls == 0
    assert repository.add_calls == []
    assert unit_of_work.commit_calls == 0


def test_missing_degraded_horizon_and_early_source_are_rejected() -> None:
    missing, _, _, missing_id = _service(FakeUnitOfWork(None, FakeRecommendationRepository()))
    with pytest.raises(RecommendationSourceNotFoundError):
        missing.create(command())
    assert missing_id.calls == 0

    degraded, _, _, _ = _service(
        FakeUnitOfWork(feature_snapshot(degraded=True), FakeRecommendationRepository())
    )
    with pytest.raises(RecommendationSourceRejectedError, match="SOURCE_NOT_READY"):
        degraded.create(command())

    allowed, _, _, _ = _service(
        FakeUnitOfWork(feature_snapshot(degraded=True), FakeRecommendationRepository())
    )
    result = allowed.create(command(disposition=RecommendationDisposition.DATA_INSUFFICIENT))
    assert result.outcome is RecommendationCreationOutcome.CREATED

    long_plan = replace(plan(), expected_holding_trading_days=TradingDayHorizon(4))
    horizon, _, _, _ = _service(FakeUnitOfWork(feature_snapshot(), FakeRecommendationRepository()))
    with pytest.raises(RecommendationSourceRejectedError, match="HORIZON_EXCEEDED"):
        horizon.create(command(selected_plan=long_plan))

    early, _, clock, _ = _service(
        FakeUnitOfWork(feature_snapshot(), FakeRecommendationRepository()),
        clock=RecordingClock(GENERATED_AT - timedelta(days=30)),
    )
    with pytest.raises(RecommendationSourceRejectedError, match="GENERATED_BEFORE_SOURCE"):
        early.create(command())
    assert clock.calls == 1


def test_unique_race_resolves_same_digest_and_rejects_other_or_missing() -> None:
    source_command = command()
    first = FakeUnitOfWork(
        feature_snapshot(),
        FakeRecommendationRepository(duplicate_on_add=True),
    )
    second = FakeUnitOfWork(
        feature_snapshot(),
        FakeRecommendationRepository(stored_recommendation(source_command)),
    )
    service, factory, clock, identifier_factory = _service(first, second)

    result = service.create(source_command)

    assert result.outcome is RecommendationCreationOutcome.ALREADY_EXISTS
    assert factory.calls == 2
    assert clock.calls == identifier_factory.calls == 1
    assert first.rollback_calls == 1
    assert first.commit_calls == second.commit_calls == 0

    other_first = FakeUnitOfWork(
        feature_snapshot(),
        FakeRecommendationRepository(duplicate_on_add=True),
    )
    other_second = FakeUnitOfWork(
        feature_snapshot(),
        FakeRecommendationRepository(
            stored_recommendation(command(reason_codes=("OTHER_REASON",)))
        ),
    )
    conflict, _, _, _ = _service(other_first, other_second)
    with pytest.raises(RecommendationConflictError):
        conflict.create(source_command)

    missing_first = FakeUnitOfWork(
        feature_snapshot(),
        FakeRecommendationRepository(duplicate_on_add=True),
    )
    missing_second = FakeUnitOfWork(feature_snapshot(), FakeRecommendationRepository())
    unresolved, _, _, _ = _service(missing_first, missing_second)
    with pytest.raises(RecommendationRaceResolutionError):
        unresolved.create(source_command)


@pytest.mark.parametrize("failure", ["get", "add"])
def test_repository_failure_rolls_back_and_does_not_expose_codes(failure: str) -> None:
    repository = FakeRecommendationRepository(failure=failure)
    unit_of_work = FakeUnitOfWork(feature_snapshot(), repository)
    service, _, _, _ = _service(unit_of_work)

    with pytest.raises(PersistenceError) as captured:
        service.create(command(reason_codes=("DO_NOT_LEAK_SECRET",)))

    assert "DO_NOT_LEAK_SECRET" not in str(captured.value)
    assert unit_of_work.rollback_calls == 1
    assert unit_of_work.commit_calls == 0


def test_wrong_command_type_stops_before_clock_or_uow() -> None:
    unit_of_work = FakeUnitOfWork(feature_snapshot(), FakeRecommendationRepository())
    service, factory, clock, identifier_factory = _service(unit_of_work)

    with pytest.raises(RecommendationValidationError):
        service.create(cast(CreateRecommendationCommand, object()))

    assert factory.calls == clock.calls == identifier_factory.calls == 0
