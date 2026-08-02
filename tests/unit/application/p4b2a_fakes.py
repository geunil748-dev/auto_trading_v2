from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID

from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.application.contracts.outcome_labels import (
    CreateDailyFeatureOutcomeLabelCommand,
    DailyFeatureOutcomeLabelCreationOutcome,
    DailyFeatureOutcomeLabelCreationResult,
    NewDailyFeatureOutcomeLabel,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.domain.calibration_datasets import (
    CalibrationDatasetPolicyCode,
    CalibrationDatasetPolicyVersion,
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.feature_outcomes import DailyFeatureOutcome
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.outcome_labels import DailyFeatureOutcomeLabel
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    ProbabilityCalibrationDatasetID,
    ProbabilityCalibrationDatasetItemID,
)


@dataclass
class CountingClock:
    value: datetime
    calls: int = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return self.value


@dataclass
class LabelIDs:
    value: int = 90_000
    calls: int = 0

    def new(self) -> DailyFeatureOutcomeLabelID:
        self.calls += 1
        return DailyFeatureOutcomeLabelID(UUID(int=self.value + self.calls))


@dataclass
class DatasetIDs:
    value: int = 91_000
    calls: int = 0

    def new(self) -> ProbabilityCalibrationDatasetID:
        self.calls += 1
        return ProbabilityCalibrationDatasetID(UUID(int=self.value + self.calls))


@dataclass
class ItemIDs:
    value: int = 92_000
    calls: int = 0

    def new(self) -> ProbabilityCalibrationDatasetItemID:
        self.calls += 1
        return ProbabilityCalibrationDatasetItemID(UUID(int=self.value + self.calls))


@dataclass
class FakeOutcomeRepository:
    values: dict[DailyFeatureOutcomeID, DailyFeatureOutcome]
    reads: int = 0

    def get_by_id(self, identifier: DailyFeatureOutcomeID) -> DailyFeatureOutcome | None:
        self.reads += 1
        return self.values.get(identifier)


@dataclass
class FakeLabelRepository:
    values: dict[str, DailyFeatureOutcomeLabel] = field(default_factory=dict)
    key_reads: int = 0
    inserts: int = 0
    duplicate_once: bool = False
    conflict_winner: bool = False

    def get_by_label_key(self, key: str) -> DailyFeatureOutcomeLabel | None:
        self.key_reads += 1
        return self.values.get(key)

    def add(self, candidate: NewDailyFeatureOutcomeLabel) -> DailyFeatureOutcomeLabel:
        self.inserts += 1
        label = candidate.label
        if self.duplicate_once:
            self.duplicate_once = False
            winner = replace(label, content_digest="f" * 64) if self.conflict_winner else label
            self.values[label.label_key] = winner
            raise DuplicateRecordError(entity="outcome_label", operation="insert")
        self.values[label.label_key] = label
        return label


@dataclass
class FakeDatasetRepository:
    values: dict[str, ProbabilityCalibrationDatasetWithItems] = field(default_factory=dict)
    key_reads: int = 0
    inserts: int = 0
    duplicate_once: bool = False
    conflict_winner: bool = False

    def get_by_dataset_key(self, key: str) -> ProbabilityCalibrationDataset | None:
        self.key_reads += 1
        aggregate = self.values.get(key)
        return None if aggregate is None else aggregate.dataset

    def get_dataset_with_items(
        self, identifier: ProbabilityCalibrationDatasetID
    ) -> ProbabilityCalibrationDatasetWithItems | None:
        return next(
            (
                aggregate
                for aggregate in self.values.values()
                if aggregate.dataset.probability_calibration_dataset_id == identifier
            ),
            None,
        )

    def add_dataset_with_items(
        self, candidate: NewProbabilityCalibrationDatasetWithItems
    ) -> ProbabilityCalibrationDatasetWithItems:
        self.inserts += 1
        aggregate = candidate.aggregate
        if self.duplicate_once:
            self.duplicate_once = False
            if self.conflict_winner:
                winner = deepcopy(aggregate)
                object.__setattr__(winner.dataset, "content_digest", "f" * 64)
            else:
                winner = aggregate
            self.values[aggregate.dataset.dataset_key] = winner
            raise DuplicateRecordError(entity="calibration_dataset", operation="insert")
        self.values[aggregate.dataset.dataset_key] = aggregate
        return aggregate


@dataclass
class FakeUnitOfWorkFactory:
    outcomes: FakeOutcomeRepository
    labels: FakeLabelRepository = field(default_factory=FakeLabelRepository)
    datasets: FakeDatasetRepository = field(default_factory=FakeDatasetRepository)
    commits: int = 0
    rollbacks: int = 0

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)


@dataclass
class FakeUnitOfWork:
    factory: FakeUnitOfWorkFactory

    def __enter__(self) -> FakeUnitOfWork:
        self.daily_feature_outcomes = self.factory.outcomes
        self.daily_feature_outcome_labels = self.factory.labels
        self.probability_calibration_datasets = self.factory.datasets
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def commit(self) -> None:
        self.factory.commits += 1

    def rollback(self) -> None:
        self.factory.rollbacks += 1


@dataclass
class FakeSourceReader:
    values: tuple[CalibrationDatasetSourceRecord, ...]
    calls: int = 0

    def list_eligible_sources(
        self,
        _horizon: TradingDayHorizon,
        _dataset_as_of: datetime,
        _dataset_policy_code: CalibrationDatasetPolicyCode,
        _dataset_policy_version: CalibrationDatasetPolicyVersion,
    ) -> tuple[CalibrationDatasetSourceRecord, ...]:
        self.calls += 1
        return self.values


@dataclass
class FakeLabelCreationService:
    values: dict[DailyFeatureOutcomeID, DailyFeatureOutcomeLabel]
    calls: int = 0

    def create(
        self, command: CreateDailyFeatureOutcomeLabelCommand
    ) -> DailyFeatureOutcomeLabelCreationResult:
        self.calls += 1
        return DailyFeatureOutcomeLabelCreationResult(
            DailyFeatureOutcomeLabelCreationOutcome.ALREADY_EXISTS,
            self.values[command.source_daily_feature_outcome_id],
        )
