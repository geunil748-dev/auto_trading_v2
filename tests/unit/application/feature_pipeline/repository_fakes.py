from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineRunWithItems
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    UniverseSnapshotID,
)
from auto_trading_v2.domain.universes import UniverseSnapshot

NOW = datetime(2026, 8, 1, 0, tzinfo=UTC)


class UniverseRepository:
    def __init__(self, snapshot: UniverseSnapshot) -> None:
        self.snapshot = snapshot

    def get_by_id(self, value: UniverseSnapshotID) -> UniverseSnapshot | None:
        return self.snapshot if value == self.snapshot.universe_snapshot_id else None


class PipelineRunRepository:
    def __init__(self) -> None:
        self.rows: dict[str, DailyFeaturePipelineRunWithItems] = {}
        self.add_calls = 0

    def get_by_run_key(self, key: str) -> Any:
        aggregate = self.rows.get(key)
        return None if aggregate is None else aggregate.run

    def get_run_with_items(self, run_id: DailyFeaturePipelineRunID) -> Any:
        return next(
            (
                aggregate
                for aggregate in self.rows.values()
                if aggregate.run.daily_feature_pipeline_run_id == run_id
            ),
            None,
        )

    def add_run_with_items(
        self,
        source: NewDailyFeaturePipelineRunWithItems,
    ) -> DailyFeaturePipelineRunWithItems:
        self.add_calls += 1
        stored = source.stored(NOW)
        self.rows[source.run.run_key] = stored
        return stored


class FakeUnitOfWork:
    def __init__(self, universe: UniverseRepository, runs: PipelineRunRepository) -> None:
        self.universe_snapshots = universe
        self.daily_feature_pipeline_runs = runs
        self.commits = 0
        self.finished = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commits += 1
        self.finished = True

    def rollback(self) -> None:
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.finished = True


class FakeUnitOfWorkFactory:
    def __init__(self, snapshot: UniverseSnapshot) -> None:
        self.universe = UniverseRepository(snapshot)
        self.runs = PipelineRunRepository()
        self.units: list[FakeUnitOfWork] = []

    def __call__(self) -> FakeUnitOfWork:
        unit = FakeUnitOfWork(self.universe, self.runs)
        self.units.append(unit)
        return unit


@dataclass
class CountingRunIDs:
    calls: int = 0

    def new(self) -> DailyFeaturePipelineRunID:
        self.calls += 1
        return DailyFeaturePipelineRunID(UUID(int=2000 + self.calls))


@dataclass
class CountingItemIDs:
    calls: int = 0

    def new(self) -> DailyFeaturePipelineItemID:
        self.calls += 1
        return DailyFeaturePipelineItemID(UUID(int=3000 + self.calls))
