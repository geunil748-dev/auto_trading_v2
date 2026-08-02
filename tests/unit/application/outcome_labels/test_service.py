from datetime import UTC, datetime
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.outcome_labels import (
    CreateDailyFeatureOutcomeLabelCommand,
    DailyFeatureOutcomeLabelCreationOutcome,
)
from auto_trading_v2.application.outcome_label_errors import (
    DailyFeatureOutcomeLabelConflictError,
    DailyFeatureOutcomeLabelSourceNotFoundError,
)
from auto_trading_v2.application.services.daily_feature_outcome_label import (
    DailyFeatureOutcomeLabelCreationService,
)
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeID
from tests.unit.application.p4b2a_fakes import (
    CountingClock,
    FakeLabelRepository,
    FakeOutcomeRepository,
    FakeUnitOfWorkFactory,
    LabelIDs,
)
from tests.unit.p4b2a_helpers import make_outcomes


def _context() -> tuple[
    DailyFeatureOutcomeLabelCreationService,
    FakeUnitOfWorkFactory,
    CountingClock,
    LabelIDs,
    object,
]:
    outcome = make_outcomes((("AAPL", "105"),))[0]
    factory = FakeUnitOfWorkFactory(
        FakeOutcomeRepository({outcome.daily_feature_outcome_id: outcome})
    )
    clock = CountingClock(datetime(2026, 8, 5, tzinfo=UTC))
    identifiers = LabelIDs()
    service = DailyFeatureOutcomeLabelCreationService(
        factory,  # type: ignore[arg-type]
        clock,
        identifiers,
    )
    return service, factory, clock, identifiers, outcome


def test_create_then_exact_retry_performs_no_source_clock_id_insert_or_commit_work() -> None:
    service, factory, clock, identifiers, outcome = _context()
    command = CreateDailyFeatureOutcomeLabelCommand(outcome.daily_feature_outcome_id)  # type: ignore[union-attr]

    created = service.create(command)
    counters = (
        factory.outcomes.reads,
        clock.calls,
        identifiers.calls,
        factory.labels.inserts,
        factory.commits,
    )
    retried = service.create(command)

    assert created.outcome is DailyFeatureOutcomeLabelCreationOutcome.CREATED
    assert retried.outcome is DailyFeatureOutcomeLabelCreationOutcome.ALREADY_EXISTS
    assert retried.label == created.label
    assert (
        factory.outcomes.reads,
        clock.calls,
        identifiers.calls,
        factory.labels.inserts,
        factory.commits,
    ) == counters
    assert counters == (1, 1, 1, 1, 1)


def test_missing_source_creates_and_commits_nothing() -> None:
    service, factory, clock, identifiers, _ = _context()
    command = CreateDailyFeatureOutcomeLabelCommand(DailyFeatureOutcomeID(UUID(int=999_999)))

    with pytest.raises(DailyFeatureOutcomeLabelSourceNotFoundError):
        service.create(command)

    assert (clock.calls, identifiers.calls, factory.labels.inserts, factory.commits) == (0, 0, 0, 0)


@pytest.mark.parametrize("conflict", [False, True])
def test_unique_race_reloads_a_fresh_winner_or_reports_safe_conflict(conflict: bool) -> None:
    service, factory, _, _, outcome = _context()
    factory.labels = FakeLabelRepository(duplicate_once=True, conflict_winner=conflict)
    command = CreateDailyFeatureOutcomeLabelCommand(outcome.daily_feature_outcome_id)  # type: ignore[union-attr]

    if conflict:
        with pytest.raises(DailyFeatureOutcomeLabelConflictError) as captured:
            service.create(command)
        assert "AAPL" not in str(captured.value)
    else:
        result = service.create(command)
        assert result.outcome is DailyFeatureOutcomeLabelCreationOutcome.ALREADY_EXISTS

    assert factory.rollbacks == 1
    assert factory.commits == 0
