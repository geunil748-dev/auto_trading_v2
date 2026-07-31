from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.universes import (
    CreateUniverseSnapshotCommand,
    NewUniverseSnapshot,
    UniverseSnapshotCreationOutcome,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.ports.id_factory import UniverseSnapshotIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.universe_snapshot import (
    UniverseSnapshotCreationService,
)
from auto_trading_v2.application.universe_errors import UniverseSnapshotConflictError
from auto_trading_v2.domain.primitives import Symbol, UniverseSnapshotID
from auto_trading_v2.domain.universes import UniverseMember, UniverseSnapshot
from auto_trading_v2.ports.clock import Clock

NOW = datetime(2026, 7, 31, 22, tzinfo=UTC)


@dataclass
class FakeClock:
    def now_utc(self) -> datetime:
        return NOW


@dataclass
class CountingIDFactory:
    calls: int = 0

    def new(self) -> UniverseSnapshotID:
        self.calls += 1
        return UniverseSnapshotID(UUID(int=self.calls))


class InMemoryUniverseRepository:
    def __init__(self) -> None:
        self.rows: dict[str, UniverseSnapshot] = {}
        self.add_calls = 0
        self.race_on_add = False

    def get_by_universe_key(self, key: str) -> UniverseSnapshot | None:
        return self.rows.get(key)

    def add(self, value: NewUniverseSnapshot) -> UniverseSnapshot:
        self.add_calls += 1
        stored = value.stored(NOW)
        if self.race_on_add:
            self.race_on_add = False
            self.rows[value.universe_key] = stored
            raise DuplicateRecordError(
                entity="universe_snapshot",
                operation="insert",
                reason="duplicate_record",
            )
        self.rows[value.universe_key] = stored
        return stored


class FakeUnitOfWork:
    def __init__(self, repository: InMemoryUniverseRepository) -> None:
        self.universe_snapshots = repository
        self.commits = 0
        self.rollbacks = 0
        self.finished = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commits += 1
        self.finished = True

    def rollback(self) -> None:
        self.rollbacks += 1
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.finished:
            self.rollback()


class FakeUnitOfWorkFactory:
    def __init__(self, repository: InMemoryUniverseRepository) -> None:
        self.repository = repository
        self.units: list[FakeUnitOfWork] = []

    def __call__(self) -> FakeUnitOfWork:
        unit = FakeUnitOfWork(self.repository)
        self.units.append(unit)
        return unit


def command(symbol: str = "AAPL") -> CreateUniverseSnapshotCommand:
    return CreateUniverseSnapshotCommand(
        "CORE_US",
        "2026-07-31",
        (UniverseMember(Symbol(symbol), "XNGS"),),
    )


def service(
    repository: InMemoryUniverseRepository,
) -> tuple[UniverseSnapshotCreationService, CountingIDFactory, FakeUnitOfWorkFactory]:
    factory = FakeUnitOfWorkFactory(repository)
    ids = CountingIDFactory()
    return (
        UniverseSnapshotCreationService(
            cast(UnitOfWorkFactory, factory),
            cast(Clock, FakeClock()),
            cast(UniverseSnapshotIDFactory, ids),
        ),
        ids,
        factory,
    )


def test_create_then_exact_retry_does_not_allocate_insert_or_commit() -> None:
    repository = InMemoryUniverseRepository()
    target, ids, factory = service(repository)

    created = target.create(command())
    retried = target.create(command())

    assert created.outcome is UniverseSnapshotCreationOutcome.CREATED
    assert retried.outcome is UniverseSnapshotCreationOutcome.ALREADY_EXISTS
    assert retried.snapshot == created.snapshot
    assert ids.calls == 1
    assert repository.add_calls == 1
    assert factory.units[0].commits == 1
    assert factory.units[1].commits == 0


def test_same_code_version_with_different_members_is_sanitized_conflict() -> None:
    repository = InMemoryUniverseRepository()
    target, _, factory = service(repository)
    target.create(command("AAPL"))

    with pytest.raises(UniverseSnapshotConflictError) as caught:
        target.create(command("MSFT"))

    assert "AAPL" not in str(caught.value)
    assert "MSFT" not in str(caught.value)
    assert repository.add_calls == 1
    assert factory.units[-1].commits == 0


def test_unique_race_rolls_back_and_resolves_with_fresh_unit_of_work() -> None:
    repository = InMemoryUniverseRepository()
    repository.race_on_add = True
    target, ids, factory = service(repository)

    result = target.create(command())

    assert result.outcome is UniverseSnapshotCreationOutcome.ALREADY_EXISTS
    assert ids.calls == 1
    assert repository.add_calls == 1
    assert factory.units[0].rollbacks == 1
    assert factory.units[1].commits == 0
