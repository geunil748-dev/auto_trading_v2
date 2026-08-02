from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from auto_trading_v2.application.contracts.feature_outcomes import (
    NewDailyFeatureOutcome,
    NewDailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBar
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcome,
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineRunWithItems
from auto_trading_v2.domain.feature_scoring import DailyFeatureScoringRunWithItems
from auto_trading_v2.domain.feature_snapshots import FeatureSnapshot
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeObservationRunID,
    DailyFeatureOutcomeObservationRunItemID,
    DailyFeatureScoringItemID,
)


@dataclass
class FakeScoringRepository:
    aggregate: DailyFeatureScoringRunWithItems | None
    reads: int = 0

    def get_run_with_items(self, _run_id: object) -> DailyFeatureScoringRunWithItems | None:
        self.reads += 1
        return self.aggregate


@dataclass
class FakePipelineRepository:
    aggregate: DailyFeaturePipelineRunWithItems | None
    reads: int = 0

    def get_run_with_items(self, _run_id: object) -> DailyFeaturePipelineRunWithItems | None:
        self.reads += 1
        return self.aggregate


@dataclass
class FakeFeatureRepository:
    values: dict[UUID, FeatureSnapshot]
    reads: int = 0

    def get_by_id(self, feature_id: object) -> FeatureSnapshot | None:
        self.reads += 1
        return self.values.get(feature_id.value)  # type: ignore[union-attr]


@dataclass
class FakeBarRepository:
    by_symbol: dict[str, tuple[DailyMarketBar, ...]]
    reads: int = 0

    def list_latest_available_for_sessions(
        self,
        _source: object,
        symbol: object,
        _basis: object,
        _sessions: object,
        _as_of: object,
    ) -> tuple[DailyMarketBar, ...]:
        self.reads += 1
        return self.by_symbol.get(symbol.value, ())  # type: ignore[union-attr]


@dataclass
class FakeOutcomeRepository:
    values: dict[str, DailyFeatureOutcome] = field(default_factory=dict)
    inserts: int = 0

    def get_by_outcome_key(self, key: str) -> DailyFeatureOutcome | None:
        return self.values.get(key)

    def add(self, candidate: NewDailyFeatureOutcome) -> DailyFeatureOutcome:
        self.inserts += 1
        self.values[candidate.outcome.outcome_key] = candidate.outcome
        return candidate.outcome


@dataclass
class FakeObservationRunRepository:
    values: dict[str, DailyFeatureOutcomeObservationRunWithItems] = field(default_factory=dict)
    inserts: int = 0

    def get_by_observation_run_key(self, key: str) -> DailyFeatureOutcomeObservationRun | None:
        aggregate = self.values.get(key)
        return None if aggregate is None else aggregate.run

    def get_run_with_items(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> DailyFeatureOutcomeObservationRunWithItems | None:
        return next(
            (
                aggregate
                for aggregate in self.values.values()
                if aggregate.run.daily_feature_outcome_observation_run_id == run_id
            ),
            None,
        )

    def add_run_with_items(
        self, candidate: NewDailyFeatureOutcomeObservationRunWithItems
    ) -> DailyFeatureOutcomeObservationRunWithItems:
        self.inserts += 1
        aggregate = candidate.aggregate
        self.values[aggregate.run.observation_run_key] = aggregate
        return aggregate


@dataclass
class FakeUnitOfWorkFactory:
    scoring: FakeScoringRepository
    pipeline: FakePipelineRepository
    features: FakeFeatureRepository
    bars: FakeBarRepository
    outcomes: FakeOutcomeRepository = field(default_factory=FakeOutcomeRepository)
    runs: FakeObservationRunRepository = field(default_factory=FakeObservationRunRepository)
    commits: int = 0
    rollbacks: int = 0

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)


@dataclass
class FakeUnitOfWork:
    factory: FakeUnitOfWorkFactory

    def __enter__(self) -> FakeUnitOfWork:
        self.daily_feature_scoring_runs = self.factory.scoring
        self.daily_feature_pipeline_runs = self.factory.pipeline
        self.feature_snapshots = self.factory.features
        self.daily_market_bars = self.factory.bars
        self.daily_feature_outcomes = self.factory.outcomes
        self.daily_feature_outcome_observation_runs = self.factory.runs
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def commit(self) -> None:
        self.factory.commits += 1

    def rollback(self) -> None:
        self.factory.rollbacks += 1


@dataclass
class OutcomeIDs:
    value: int = 10_000

    def new(self) -> DailyFeatureOutcomeID:
        self.value += 1
        return DailyFeatureOutcomeID(UUID(int=self.value))


@dataclass
class RunIDs:
    value: int = 20_000

    def new(self) -> DailyFeatureOutcomeObservationRunID:
        self.value += 1
        return DailyFeatureOutcomeObservationRunID(UUID(int=self.value))


@dataclass
class RunItemIDs:
    value: int = 30_000

    def new(self) -> DailyFeatureOutcomeObservationRunItemID:
        self.value += 1
        return DailyFeatureOutcomeObservationRunItemID(UUID(int=self.value))


def source_ids(
    aggregate: DailyFeatureScoringRunWithItems,
) -> tuple[DailyFeatureScoringItemID, ...]:
    return tuple(item.daily_feature_scoring_item_id for item in aggregate.items)
