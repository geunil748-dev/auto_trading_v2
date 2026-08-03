from decimal import Decimal
from typing import cast

import pytest

from auto_trading_v2.application.contracts.daily_market_bars import (
    DailyMarketBarCreationOutcome,
)
from auto_trading_v2.application.daily_market_bar_errors import (
    DailyMarketBarConflictError,
    DailyMarketBarRaceResolutionError,
)
from auto_trading_v2.application.ports.id_factory import DailyMarketBarIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_market_bar import (
    DailyMarketBarCreationService,
)
from tests.unit.application.daily_market_bars.fakes import (
    FakeDailyMarketBarRepository,
    FakeUnitOfWork,
    RecordingIDFactory,
    SequencedUnitOfWorkFactory,
    command,
    stored,
)


def _service(
    factory: SequencedUnitOfWorkFactory,
    identifiers: RecordingIDFactory,
) -> DailyMarketBarCreationService:
    return DailyMarketBarCreationService(
        cast(UnitOfWorkFactory, factory),
        cast(DailyMarketBarIDFactory, identifiers),
    )


def test_created_inserts_and_commits_exactly_once() -> None:
    repository = FakeDailyMarketBarRepository()
    unit = FakeUnitOfWork(repository)
    factory = SequencedUnitOfWorkFactory(unit)
    identifiers = RecordingIDFactory()

    result = _service(factory, identifiers).create(command())

    assert result.outcome is DailyMarketBarCreationOutcome.CREATED
    assert identifiers.calls == 1
    assert len(repository.add_calls) == 1
    assert unit.commit_calls == 1
    assert unit.rollback_calls == 0


def test_exact_retry_has_no_id_insert_or_commit() -> None:
    source = command()
    repository = FakeDailyMarketBarRepository(stored(source))
    unit = FakeUnitOfWork(repository)
    identifiers = RecordingIDFactory()

    result = _service(SequencedUnitOfWorkFactory(unit), identifiers).create(source)

    assert result.outcome is DailyMarketBarCreationOutcome.ALREADY_EXISTS
    assert identifiers.calls == 0
    assert repository.add_calls == []
    assert unit.commit_calls == 0


def test_same_identity_with_different_content_is_sanitized_conflict() -> None:
    existing_command = command()
    repository = FakeDailyMarketBarRepository(stored(existing_command))
    unit = FakeUnitOfWork(repository)
    identifiers = RecordingIDFactory()

    with pytest.raises(DailyMarketBarConflictError) as captured:
        _service(SequencedUnitOfWorkFactory(unit), identifiers).create(
            command(close_price=Decimal(101))
        )

    assert "bar-000" not in str(captured.value)
    assert identifiers.calls == 0
    assert repository.add_calls == []
    assert unit.commit_calls == 0


def test_unique_race_same_digest_rolls_back_and_returns_existing() -> None:
    source = command()
    first_repo = FakeDailyMarketBarRepository(duplicate_on_add=True)
    second_repo = FakeDailyMarketBarRepository(stored(source, 2))
    first = FakeUnitOfWork(first_repo)
    second = FakeUnitOfWork(second_repo)
    factory = SequencedUnitOfWorkFactory(first, second)
    identifiers = RecordingIDFactory()

    result = _service(factory, identifiers).create(source)

    assert result.outcome is DailyMarketBarCreationOutcome.ALREADY_EXISTS
    assert factory.calls == 2
    assert first.rollback_calls == 1
    assert first.commit_calls == second.commit_calls == 0
    assert identifiers.calls == 1


def test_unique_race_different_digest_is_conflict() -> None:
    source = command()
    first = FakeUnitOfWork(FakeDailyMarketBarRepository(duplicate_on_add=True))
    second = FakeUnitOfWork(
        FakeDailyMarketBarRepository(stored(command(close_price=Decimal(101)), 2))
    )

    with pytest.raises(DailyMarketBarConflictError):
        _service(
            SequencedUnitOfWorkFactory(first, second),
            RecordingIDFactory(),
        ).create(source)

    assert first.rollback_calls == 1
    assert second.commit_calls == 0


def test_unique_race_without_readable_row_is_resolution_error() -> None:
    first = FakeUnitOfWork(FakeDailyMarketBarRepository(duplicate_on_add=True))
    second = FakeUnitOfWork(FakeDailyMarketBarRepository())

    with pytest.raises(DailyMarketBarRaceResolutionError):
        _service(
            SequencedUnitOfWorkFactory(first, second),
            RecordingIDFactory(),
        ).create(command())
