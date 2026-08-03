from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from uuid import UUID

import pytest

from auto_trading_v2.adapters.identifiers import UuidFilterEvaluationIDFactory
from auto_trading_v2.application.contracts.persistence import (
    NewFilterEvaluation,
    StoredCandidate,
    StoredFilterEvaluation,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.errors import (
    CandidateNotFoundError,
    DuplicateRecordError,
    FilterEvaluationConflictError,
    MarketSnapshotNotFoundError,
    PersistenceError,
)
from auto_trading_v2.application.services.filter_evaluation import (
    CandidateFilterEvaluationService,
)
from auto_trading_v2.domain.filtering.catalog import BUILT_IN_FILTER_SETS
from auto_trading_v2.domain.primitives import (
    CandidateID,
    FilterEvaluationID,
    IdentifierFactory,
    MarketSnapshotID,
    Price,
    RunID,
    SessionDate,
    Symbol,
)

NOW = datetime(2026, 7, 14, 1, tzinfo=UTC)
CANDIDATE_ID = CandidateID(UUID(int=101))
SNAPSHOT_ID = MarketSnapshotID(UUID(int=102))


def _snapshot() -> StoredMarketSnapshot:
    return StoredMarketSnapshot(
        market_snapshot_id=SNAPSHOT_ID,
        symbol=Symbol("AAPL"),
        session_date=SessionDate(date(2026, 7, 14)),
        observed_at=NOW,
        source="TEST",
        open_price=Price(Decimal("22.66")),
        high_price=Price(Decimal("26")),
        low_price=Price(Decimal("20")),
        last_price=Price(Decimal("25")),
        previous_high_price=Price(Decimal("20")),
        previous_low_price=Price(Decimal("10")),
        previous_close_price=Price(Decimal("22")),
        volume=100,
        recorded_at=NOW,
    )


def _candidate() -> StoredCandidate:
    return StoredCandidate(
        candidate_id=CANDIDATE_ID,
        run_id=RunID(UUID(int=103)),
        market_snapshot_id=SNAPSHOT_ID,
        candidate_source="TEST",
        rank=None,
        source_score=None,
        selected_at=NOW,
        recorded_at=NOW,
    )


class FakeCandidateRepository:
    def __init__(self, candidate: StoredCandidate | None) -> None:
        self.candidate = candidate
        self.requested: list[CandidateID] = []

    def get(self, candidate_id: CandidateID) -> StoredCandidate | None:
        self.requested.append(candidate_id)
        return self.candidate


class FakeMarketSnapshotRepository:
    def __init__(self, snapshot: StoredMarketSnapshot | None) -> None:
        self.snapshot = snapshot
        self.requested: list[MarketSnapshotID] = []

    def get(self, snapshot_id: MarketSnapshotID) -> StoredMarketSnapshot | None:
        self.requested.append(snapshot_id)
        return self.snapshot


class FakeFilterEvaluationRepository:
    def __init__(
        self,
        *,
        duplicate_on: int | None = None,
        failure_on: int | None = None,
    ) -> None:
        self.duplicate_on = duplicate_on
        self.failure_on = failure_on
        self.attempted: list[NewFilterEvaluation] = []
        self.pending: list[StoredFilterEvaluation] = []

    def add(self, evaluation: NewFilterEvaluation) -> StoredFilterEvaluation:
        self.attempted.append(evaluation)
        position = len(self.attempted)
        if position == self.duplicate_on:
            raise DuplicateRecordError(
                entity="filter_evaluation",
                operation="insert",
                reason="duplicate_record",
            )
        if position == self.failure_on:
            raise PersistenceError(entity="filter_evaluation", operation="insert")
        stored = StoredFilterEvaluation(
            filter_evaluation_id=evaluation.filter_evaluation_id,
            candidate_id=evaluation.candidate_id,
            filter_set_id=evaluation.filter_set_id,
            evaluation_version=evaluation.evaluation_version,
            passed=evaluation.passed,
            score=evaluation.score,
            details=evaluation.details,
            evaluated_at=evaluation.evaluated_at,
            recorded_at=NOW,
        )
        self.pending.append(stored)
        return stored


class FakeUnitOfWork:
    def __init__(
        self,
        candidate: StoredCandidate | None = None,
        snapshot: StoredMarketSnapshot | None = None,
        *,
        duplicate_on: int | None = None,
        failure_on: int | None = None,
    ) -> None:
        self.candidates = FakeCandidateRepository(candidate)
        self.market_snapshots = FakeMarketSnapshotRepository(snapshot)
        self.filter_evaluations = FakeFilterEvaluationRepository(
            duplicate_on=duplicate_on,
            failure_on=failure_on,
        )
        self.commits = 0
        self.rollbacks = 0
        self.active = False

    def __enter__(self) -> FakeUnitOfWork:
        self.active = True
        return self

    def commit(self) -> None:
        self.commits += 1
        self.active = False

    def rollback(self) -> None:
        self.rollbacks += 1
        self.filter_evaluations.pending.clear()
        self.active = False

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.active:
            self.rollback()


class FakeUnitOfWorkFactory:
    def __init__(self, unit_of_work: FakeUnitOfWork) -> None:
        self.unit_of_work = unit_of_work
        self.calls = 0

    def __call__(self) -> FakeUnitOfWork:
        self.calls += 1
        return self.unit_of_work


@dataclass
class FakeClock:
    current: datetime = NOW
    calls: int = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return self.current


class FakeFilterEvaluationIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> FilterEvaluationID:
        self.calls += 1
        return FilterEvaluationID(UUID(int=200 + self.calls))


def _service(
    unit_of_work: FakeUnitOfWork,
) -> tuple[
    CandidateFilterEvaluationService,
    FakeUnitOfWorkFactory,
    FakeClock,
    FakeFilterEvaluationIDFactory,
]:
    factory = FakeUnitOfWorkFactory(unit_of_work)
    clock = FakeClock()
    ids = FakeFilterEvaluationIDFactory()
    service = CandidateFilterEvaluationService(factory, clock, ids)  # type: ignore[arg-type]
    return service, factory, clock, ids


def test_service_reads_once_stores_four_and_commits_once_in_catalog_order() -> None:
    unit_of_work = FakeUnitOfWork(_candidate(), _snapshot())
    service, factory, clock, ids = _service(unit_of_work)

    batch = service.evaluate_all(CANDIDATE_ID)

    assert factory.calls == 1
    assert unit_of_work.candidates.requested == [CANDIDATE_ID]
    assert unit_of_work.market_snapshots.requested == [SNAPSHOT_ID]
    assert clock.calls == 1
    assert ids.calls == 4
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0
    assert len(batch.evaluations) == 4
    assert tuple(item.filter_set_id for item in batch.evaluations) == tuple(
        item.filter_set_id for item in BUILT_IN_FILTER_SETS
    )
    assert {item.evaluated_at for item in batch.evaluations} == {NOW}


def test_missing_candidate_and_snapshot_raise_safe_errors_without_commit() -> None:
    missing_candidate = FakeUnitOfWork(None, None)
    service, _, clock, ids = _service(missing_candidate)
    with pytest.raises(CandidateNotFoundError):
        service.evaluate_all(CANDIDATE_ID)
    assert missing_candidate.commits == 0
    assert missing_candidate.rollbacks == 1
    assert clock.calls == 0
    assert ids.calls == 0

    missing_snapshot = FakeUnitOfWork(_candidate(), None)
    service, _, clock, ids = _service(missing_snapshot)
    with pytest.raises(MarketSnapshotNotFoundError):
        service.evaluate_all(CANDIDATE_ID)
    assert missing_snapshot.commits == 0
    assert missing_snapshot.rollbacks == 1
    assert clock.calls == 0
    assert ids.calls == 0


def test_duplicate_translates_to_safe_conflict_and_rolls_back_batch() -> None:
    unit_of_work = FakeUnitOfWork(_candidate(), _snapshot(), duplicate_on=2)
    service, _, clock, ids = _service(unit_of_work)

    with pytest.raises(FilterEvaluationConflictError) as caught:
        service.evaluate_all(CANDIDATE_ID)

    assert caught.value.filter_set_name.value == "BALANCED"
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
    assert unit_of_work.filter_evaluations.pending == []
    assert len(unit_of_work.filter_evaluations.attempted) == 2
    assert clock.calls == 1
    assert ids.calls == 2
    assert "SQL" not in str(caught.value)
    assert "parameter" not in str(caught.value)


def test_mid_batch_persistence_error_stops_later_evaluations_and_rolls_back() -> None:
    unit_of_work = FakeUnitOfWork(_candidate(), _snapshot(), failure_on=3)
    service, _, _, ids = _service(unit_of_work)

    with pytest.raises(PersistenceError):
        service.evaluate_all(CANDIDATE_ID)

    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1
    assert unit_of_work.filter_evaluations.pending == []
    assert len(unit_of_work.filter_evaluations.attempted) == 3
    assert ids.calls == 3


def test_production_id_adapter_reuses_existing_typed_id_policy() -> None:
    expected = UUID(int=999)
    adapter = UuidFilterEvaluationIDFactory(IdentifierFactory(lambda: expected))

    assert adapter.new() == FilterEvaluationID(expected)
