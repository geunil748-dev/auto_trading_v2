"""Atomic idempotent creation of immutable UniverseSnapshot records."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.universes import (
    CreateUniverseSnapshotCommand,
    NewUniverseSnapshot,
    UniverseSnapshotCreationOutcome,
    UniverseSnapshotCreationResult,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.ports.id_factory import UniverseSnapshotIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.universe_errors import (
    UniverseSnapshotConflictError,
    UniverseSnapshotRaceResolutionError,
)
from auto_trading_v2.domain.universes import (
    UniverseSnapshot,
    UniverseSnapshotValidationError,
    universe_content_digest,
    universe_key,
)
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UniverseSnapshotCreationService:
    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    universe_snapshot_id_factory: UniverseSnapshotIDFactory

    def create(self, command: CreateUniverseSnapshotCommand) -> UniverseSnapshotCreationResult:
        if not isinstance(command, CreateUniverseSnapshotCommand):
            raise UniverseSnapshotValidationError("UNIVERSE_COMMAND_INVALID")
        definition = command.definition
        key = universe_key(definition)
        digest = universe_content_digest(definition)
        raced = False
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.universe_snapshots.get_by_universe_key(key)
            if existing is not None:
                return self._existing(existing, digest)
            new_snapshot = NewUniverseSnapshot(
                self.universe_snapshot_id_factory.new(),
                key,
                digest,
                definition,
                self.clock.now_utc(),
            )
            try:
                stored = unit_of_work.universe_snapshots.add(new_snapshot)
            except DuplicateRecordError:
                unit_of_work.rollback()
                raced = True
            else:
                unit_of_work.commit()
                return UniverseSnapshotCreationResult(
                    UniverseSnapshotCreationOutcome.CREATED,
                    stored,
                )
        if not raced:
            raise UniverseSnapshotRaceResolutionError()
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.universe_snapshots.get_by_universe_key(key)
            if existing is None:
                raise UniverseSnapshotRaceResolutionError()
            return self._existing(existing, digest)

    @staticmethod
    def _existing(
        existing: UniverseSnapshot,
        content_digest: str,
    ) -> UniverseSnapshotCreationResult:
        if existing.content_digest != content_digest:
            raise UniverseSnapshotConflictError()
        return UniverseSnapshotCreationResult(
            UniverseSnapshotCreationOutcome.ALREADY_EXISTS,
            existing,
        )
