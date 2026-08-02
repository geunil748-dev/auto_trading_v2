from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.services.daily_feature_scoring import DailyFeatureScoringService
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunStatus,
    DailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.feature_scoring import DailyFeatureScoringRunWithItems
from auto_trading_v2.domain.feature_snapshots import FeatureSnapshot
from auto_trading_v2.domain.primitives import (
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
)

from .source_fixtures import NOW, pipeline_aggregate, snapshot


@dataclass
class FakePipelineRepository:
    aggregate: DailyFeaturePipelineRunWithItems | None
    get_by_id_calls: int = 0
    aggregate_calls: int = 0

    def get_by_id(self, _run_id: object) -> DailyFeaturePipelineRun | None:
        self.get_by_id_calls += 1
        return None if self.aggregate is None else self.aggregate.run

    def get_run_with_items(self, _run_id: object) -> DailyFeaturePipelineRunWithItems | None:
        self.aggregate_calls += 1
        return self.aggregate


@dataclass
class FakeFeatureSnapshotRepository:
    snapshots: dict[UUID, FeatureSnapshot]
    calls: int = 0

    def get_by_id(self, feature_snapshot_id: object) -> FeatureSnapshot | None:
        self.calls += 1
        return self.snapshots.get(feature_snapshot_id.value)  # type: ignore[union-attr]


@dataclass
class FakeScoringRepository:
    aggregate: DailyFeatureScoringRunWithItems | None = None
    key_reads: int = 0
    aggregate_reads: int = 0
    add_calls: int = 0
    duplicate_on_add: bool = False
    conflicting_digest: bool = False

    def get_by_scoring_run_key(self, _key: str) -> object:
        self.key_reads += 1
        return None if self.aggregate is None else self.aggregate.run

    def get_run_with_items(self, _run_id: object) -> DailyFeatureScoringRunWithItems | None:
        self.aggregate_reads += 1
        return self.aggregate

    def add_run_with_items(self, aggregate: object) -> DailyFeatureScoringRunWithItems:
        self.add_calls += 1
        stored = aggregate.stored(NOW)  # type: ignore[union-attr]
        if self.duplicate_on_add:
            self.aggregate = stored
            if self.conflicting_digest:
                object.__setattr__(stored.run, "content_digest", "f" * 64)
            raise DuplicateRecordError(
                entity="daily_feature_scoring_run",
                operation="insert",
                reason="duplicate_record",
            )
        self.aggregate = stored
        return stored


@dataclass
class FakeUnitOfWorkFactory:
    pipeline: FakePipelineRepository
    features: FakeFeatureSnapshotRepository
    scoring: FakeScoringRepository = field(default_factory=FakeScoringRepository)
    commits: int = 0
    rollbacks: int = 0

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)


@dataclass
class FakeUnitOfWork:
    factory: FakeUnitOfWorkFactory

    def __enter__(self) -> FakeUnitOfWork:
        self.daily_feature_pipeline_runs = self.factory.pipeline
        self.feature_snapshots = self.factory.features
        self.daily_feature_scoring_runs = self.factory.scoring
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def commit(self) -> None:
        self.factory.commits += 1

    def rollback(self) -> None:
        self.factory.rollbacks += 1


@dataclass
class RunIDs:
    calls: int = 0

    def new(self) -> DailyFeatureScoringRunID:
        self.calls += 1
        return DailyFeatureScoringRunID(UUID(int=500 + self.calls))


@dataclass
class ItemIDs:
    calls: int = 0

    def new(self) -> DailyFeatureScoringItemID:
        self.calls += 1
        return DailyFeatureScoringItemID(UUID(int=600 + self.calls))


@dataclass(frozen=True, slots=True)
class ServiceContext:
    service: DailyFeatureScoringService
    factory: FakeUnitOfWorkFactory
    run_ids: RunIDs
    item_ids: ItemIDs


def service_context(
    specs: tuple[tuple[str, DailyFeaturePipelineItemOutcome], ...],
    *,
    status: DailyFeaturePipelineRunStatus = DailyFeaturePipelineRunStatus.COMPLETED,
) -> ServiceContext:
    aggregate, snapshots = pipeline_aggregate(specs, status=status)
    factory = FakeUnitOfWorkFactory(
        FakePipelineRepository(aggregate),
        FakeFeatureSnapshotRepository(snapshots),
    )
    run_ids = RunIDs()
    item_ids = ItemIDs()
    return ServiceContext(
        DailyFeatureScoringService(factory, FixedClock(NOW), run_ids, item_ids),  # type: ignore[arg-type]
        factory,
        run_ids,
        item_ids,
    )


__all__ = ["FakePipelineRepository", "service_context", "snapshot"]
