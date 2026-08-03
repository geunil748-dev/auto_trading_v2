from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.application.contracts.training_readiness import (
    TrainingReadinessLineageRecord,
)
from auto_trading_v2.application.services.probability_calibration_dataset_builder import (
    build_calibration_dataset,
    validate_and_order_sources,
)
from auto_trading_v2.application.services.training_readiness import (
    TrainingReadinessAuditService,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetItem,
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.primitives import (
    ProbabilityCalibrationDatasetID,
    ProbabilityCalibrationDatasetItemID,
)
from tests.unit.p4b2a_helpers import (
    GENERATED_AT,
    dataset_identity,
    make_label,
    make_outcomes,
    make_source,
)


@dataclass
class DatasetIDs:
    value: int = 700_000

    def new(self) -> ProbabilityCalibrationDatasetID:
        self.value += 1
        return ProbabilityCalibrationDatasetID(UUID(int=self.value))


@dataclass
class ItemIDs:
    value: int = 710_000

    def new(self) -> ProbabilityCalibrationDatasetItemID:
        self.value += 1
        return ProbabilityCalibrationDatasetItemID(UUID(int=self.value))


def aggregate() -> ProbabilityCalibrationDatasetWithItems:
    outcomes = make_outcomes((("MSFT", "95"), ("AAPL", "105")))
    sources = validate_and_order_sources(
        (make_source(outcomes[0], rank=2), make_source(outcomes[1], rank=1)),
        dataset_identity(),
    )
    labels_by_outcome = {
        outcome.daily_feature_outcome_id: make_label(outcome, identifier=720_000 + index)
        for index, outcome in enumerate(outcomes, 1)
    }
    labels = tuple(labels_by_outcome[source.source_daily_feature_outcome_id] for source in sources)
    return build_calibration_dataset(
        dataset_identity(), sources, labels, GENERATED_AT, DatasetIDs(), ItemIDs()
    )


def lineage_record(
    item: ProbabilityCalibrationDatasetItem,
    *,
    scoring_outcome: str = "SCORED_READY",
    source_quality_status: str | None = "READY",
    pipeline_outcome: str = "READY",
    feature_quality_status: str | None = "READY",
    quality_reason_codes: tuple[str, ...] = (),
    score: Decimal | None = Decimal("75.5"),
    rank: int | None = 1,
    has_any_outcome: bool = True,
    has_as_of_outcome: bool = True,
    has_provider_outcome: bool = True,
    has_calendar_outcome: bool = True,
    has_policy_outcome: bool = True,
    has_any_label: bool = True,
    has_matching_label: bool = True,
    provider_code: str | None = None,
) -> TrainingReadinessLineageRecord:
    identity = dataset_identity()
    return TrainingReadinessLineageRecord(
        source_daily_feature_scoring_item_id=item.source_daily_feature_scoring_item_id,
        symbol=item.symbol,
        mic_code=item.mic_code,
        source_session_date=item.source_session_date.value,
        provider_code=provider_code or identity.provider_code,
        calendar_code=identity.calendar_code.value,
        calendar_version=identity.calendar_version.value,
        scoring_policy_code=identity.scoring_policy_code.value,
        scoring_policy_version=identity.scoring_policy_version.value,
        ranking_policy_code=identity.ranking_policy_code.value,
        ranking_policy_version=identity.ranking_policy_version.value,
        scoring_outcome=scoring_outcome,
        source_quality_status=source_quality_status,
        pipeline_outcome=pipeline_outcome,
        feature_quality_status=feature_quality_status,
        quality_reason_codes=quality_reason_codes,
        overall_relative_score=score,
        source_rank=rank,
        has_any_outcome=has_any_outcome,
        has_as_of_outcome=has_as_of_outcome,
        has_provider_outcome=has_provider_outcome,
        has_calendar_outcome=has_calendar_outcome,
        has_policy_outcome=has_policy_outcome,
        has_any_label=has_any_label,
        has_matching_label=has_matching_label,
    )


class FakeRepository:
    def __init__(
        self,
        value: ProbabilityCalibrationDatasetWithItems | None,
        records: tuple[TrainingReadinessLineageRecord, ...] = (),
    ) -> None:
        self.value = value
        self.records = records
        self.reads = 0
        self.writes = 0

    def get_by_id(self, identifier: object) -> object | None:
        self.reads += 1
        if self.value is None:
            return None
        return self.value.dataset

    def list_items(self, identifier: object) -> tuple[object, ...]:
        self.reads += 1
        return () if self.value is None else self.value.items

    def list_training_readiness_lineage(self, dataset: object) -> tuple[object, ...]:
        self.reads += 1
        return self.records


class FakeUnitOfWork:
    def __init__(self, factory: "FakeUnitOfWorkFactory") -> None:
        self.factory = factory
        self.probability_calibration_datasets = factory.repository

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(self, *args: object) -> None:
        self.factory.rollbacks += 1

    def commit(self) -> None:
        self.factory.commits += 1


class FakeUnitOfWorkFactory:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.commits = 0
        self.rollbacks = 0

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)


def service_context() -> tuple[
    TrainingReadinessAuditService,
    FakeUnitOfWorkFactory,
    ProbabilityCalibrationDatasetWithItems,
]:
    value = aggregate()
    records = tuple(lineage_record(item) for item in value.items)
    factory = FakeUnitOfWorkFactory(FakeRepository(value, records))
    service = TrainingReadinessAuditService(
        factory,  # type: ignore[arg-type]
        FixedClock(datetime(2026, 8, 7, tzinfo=UTC)),
    )
    return service, factory, value
