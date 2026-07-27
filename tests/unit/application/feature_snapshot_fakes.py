from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    NewFeatureSnapshot,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshot,
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID, Symbol

AS_OF = datetime(2026, 7, 20, 15, tzinfo=UTC)
GENERATED_AT = datetime(2026, 7, 20, 15, 0, 1, tzinfo=UTC)


def command(feature_values: dict[str, object] | None = None) -> CreateFeatureSnapshotCommand:
    return CreateFeatureSnapshotCommand(
        symbol=Symbol("AAPL"),
        feature_set_code="PRICE_TECHNICAL",
        feature_set_version="v1",
        horizon=TradingDayHorizon(3),
        as_of=AS_OF,
        feature_values={"close": 100} if feature_values is None else feature_values,
        provenance=(
            FeatureProvenanceEntry(
                source_code="UNIT_TEST",
                source_record_key="row-1",
                observed_at=AS_OF,
                available_at=AS_OF,
                content_digest="a" * 64,
                source_version="v1",
            ),
        ),
        quality_status=FeatureQualityStatus.READY,
    )


def stored_for(
    source: CreateFeatureSnapshotCommand,
    *,
    identifier: int = 1,
    generated_at: datetime = GENERATED_AT,
) -> FeatureSnapshot:
    snapshot_input = source.snapshot_input
    return NewFeatureSnapshot(
        feature_snapshot_id=FeatureSnapshotID(UUID(int=identifier)),
        snapshot_key=feature_snapshot_key(snapshot_input),
        content_digest=feature_content_digest(snapshot_input),
        snapshot_input=snapshot_input,
        generated_at=generated_at,
    ).stored(generated_at)


class RecordingClock:
    def __init__(self, value: datetime = GENERATED_AT) -> None:
        self.value = value
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return self.value


class RecordingIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> FeatureSnapshotID:
        self.calls += 1
        return FeatureSnapshotID(UUID(int=100 + self.calls))


class FakeFeatureSnapshotRepository:
    def __init__(
        self,
        existing: FeatureSnapshot | None = None,
        *,
        duplicate_on_add: bool = False,
        error_on_get: bool = False,
        error_on_add: bool = False,
    ) -> None:
        self.existing = existing
        self.duplicate_on_add = duplicate_on_add
        self.error_on_get = error_on_get
        self.error_on_add = error_on_add
        self.add_calls: list[NewFeatureSnapshot] = []
        self.get_calls: list[str] = []

    def get_by_snapshot_key(self, snapshot_key: str) -> FeatureSnapshot | None:
        self.get_calls.append(snapshot_key)
        if self.error_on_get:
            raise PersistenceError(entity="feature_snapshot", operation="select")
        if self.existing is not None and self.existing.snapshot_key == snapshot_key:
            return self.existing
        return None

    def add(self, snapshot: NewFeatureSnapshot) -> FeatureSnapshot:
        self.add_calls.append(snapshot)
        if self.error_on_add:
            raise PersistenceError(entity="feature_snapshot", operation="insert")
        if self.duplicate_on_add:
            raise DuplicateRecordError(
                entity="feature_snapshot",
                operation="insert",
                reason="duplicate_record",
            )
        self.existing = snapshot.stored(GENERATED_AT)
        return self.existing


class FakeUnitOfWork:
    def __init__(self, repository: FakeFeatureSnapshotRepository) -> None:
        self.feature_snapshots = repository
        self.commit_calls = 0
        self.rollback_calls = 0
        self.finished = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1
        self.finished = True

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.finished:
            self.rollback()


@dataclass
class FakeUnitOfWorkFactory:
    unit_of_works: list[FakeUnitOfWork]
    calls: int = 0

    def __call__(self) -> FakeUnitOfWork:
        result = self.unit_of_works[self.calls]
        self.calls += 1
        return result
