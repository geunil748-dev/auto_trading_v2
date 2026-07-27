"""Atomic, idempotent Point-in-Time FeatureSnapshot creation."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    FeatureSnapshotCreationOutcome,
    FeatureSnapshotCreationResult,
    NewFeatureSnapshot,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.feature_snapshot_errors import (
    FeatureSnapshotConflictError,
    FeatureSnapshotRaceResolutionError,
)
from auto_trading_v2.application.ports.id_factory import FeatureSnapshotIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import (
    FeatureSnapshot,
    FeatureSnapshotValidationError,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class FeatureSnapshotCreationService:
    """Create once, return exact retries, and reject content mismatches."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    feature_snapshot_id_factory: FeatureSnapshotIDFactory

    def create(self, command: CreateFeatureSnapshotCommand) -> FeatureSnapshotCreationResult:
        if not isinstance(command, CreateFeatureSnapshotCommand):
            raise FeatureSnapshotValidationError("FeatureSnapshot 생성 command가 필요합니다.")
        snapshot_input = command.snapshot_input
        try:
            generated_at = normalize_utc(self.clock.now_utc())
        except ValidationError:
            raise FeatureSnapshotValidationError(
                "generated_at은 timezone-aware datetime이어야 합니다."
            ) from None
        if generated_at < snapshot_input.as_of:
            raise FeatureSnapshotValidationError("generated_at은 as_of 이전일 수 없습니다.")
        snapshot_key = feature_snapshot_key(snapshot_input)
        content_digest = feature_content_digest(snapshot_input)

        raced = False
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.feature_snapshots.get_by_snapshot_key(snapshot_key)
            if existing is not None:
                return self._existing_result(existing, content_digest)
            new_snapshot = NewFeatureSnapshot(
                feature_snapshot_id=self.feature_snapshot_id_factory.new(),
                snapshot_key=snapshot_key,
                content_digest=content_digest,
                snapshot_input=snapshot_input,
                generated_at=generated_at,
            )
            try:
                stored = unit_of_work.feature_snapshots.add(new_snapshot)
            except DuplicateRecordError:
                unit_of_work.rollback()
                raced = True
            else:
                unit_of_work.commit()
                return FeatureSnapshotCreationResult(
                    FeatureSnapshotCreationOutcome.CREATED,
                    stored,
                )
        if not raced:
            raise FeatureSnapshotRaceResolutionError()
        return self._resolve_unique_race(snapshot_key, content_digest)

    def _resolve_unique_race(
        self,
        snapshot_key: str,
        content_digest: str,
    ) -> FeatureSnapshotCreationResult:
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.feature_snapshots.get_by_snapshot_key(snapshot_key)
            if existing is None:
                raise FeatureSnapshotRaceResolutionError()
            return self._existing_result(existing, content_digest)

    @staticmethod
    def _existing_result(
        existing: FeatureSnapshot,
        content_digest: str,
    ) -> FeatureSnapshotCreationResult:
        if existing.content_digest != content_digest:
            raise FeatureSnapshotConflictError(existing.snapshot_key)
        return FeatureSnapshotCreationResult(
            FeatureSnapshotCreationOutcome.ALREADY_EXISTS,
            existing,
        )
