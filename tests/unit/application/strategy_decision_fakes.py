from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.persistence import (
    StoredCandidate,
    StoredFilterEvaluation,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.application.services.strategy_decision import (
    CandidateStrategyDecisionService,
)
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    MarketSnapshotID,
    RunID,
)
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES

NOW = datetime(2026, 7, 14, 6, 30, tzinfo=UTC)
CANDIDATE_ID = CandidateID(UUID("11111111-1111-4111-8111-111111111111"))


def candidate() -> StoredCandidate:
    return StoredCandidate(
        candidate_id=CANDIDATE_ID,
        run_id=RunID(UUID("22222222-2222-4222-8222-222222222222")),
        market_snapshot_id=MarketSnapshotID(UUID("33333333-3333-4333-8333-333333333333")),
        candidate_source="UNIT_TEST",
        rank=1,
        source_score=None,
        selected_at=NOW,
        recorded_at=NOW,
    )


def evaluation_batch() -> list[StoredFilterEvaluation]:
    return [
        StoredFilterEvaluation(
            filter_evaluation_id=FilterEvaluationID(UUID(int=100 + index)),
            candidate_id=CANDIDATE_ID,
            filter_set_id=definition.source_filter_set_id,
            evaluation_version=definition.source_evaluation_version,
            passed=True,
            score=Decimal("100"),
            details={"blocking_reason_codes": []},
            evaluated_at=NOW,
            recorded_at=NOW,
        )
        for index, definition in enumerate(BUILT_IN_STRATEGIES)
    ]


class RecordingClock:
    def __init__(self) -> None:
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return NOW


class FakeDecisionIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> DecisionID:
        value = DecisionID(UUID(int=200 + self.calls))
        self.calls += 1
        return value


class FakeCandidateRepository:
    def __init__(self, stored: StoredCandidate | None) -> None:
        self.stored = stored
        self.get_calls: list[CandidateID] = []

    def get(self, candidate_id: CandidateID) -> StoredCandidate | None:
        self.get_calls.append(candidate_id)
        return self.stored


class FakeFilterEvaluationRepository:
    def __init__(self, evaluations: Sequence[StoredFilterEvaluation]) -> None:
        self.evaluations = tuple(evaluations)
        self.list_calls: list[CandidateID] = []

    def list_by_candidate(self, candidate_id: CandidateID) -> Sequence[StoredFilterEvaluation]:
        self.list_calls.append(candidate_id)
        return self.evaluations


class FakeStrategyDecisionRepository:
    def __init__(
        self,
        *,
        failure_call: int | None = None,
        failure: PersistenceError | None = None,
    ) -> None:
        self.failure_call = failure_call
        self.failure = failure
        self.add_calls: list[NewCandidateStrategyDecision] = []
        self.pending: list[StoredCandidateStrategyDecision] = []

    def add(self, decision: NewCandidateStrategyDecision) -> StoredCandidateStrategyDecision:
        self.add_calls.append(decision)
        if self.failure_call == len(self.add_calls):
            if self.failure is not None:
                raise self.failure
            raise DuplicateRecordError(
                entity="strategy_decision",
                operation="insert",
                reason="duplicate_record",
            )
        stored = StoredCandidateStrategyDecision(
            decision_id=decision.decision_id,
            decision_key=decision.decision_key,
            candidate_id=decision.candidate_id,
            filter_evaluation_id=decision.filter_evaluation_id,
            strategy_id=decision.strategy_id,
            strategy_version=decision.strategy_version,
            action=decision.action,
            reason_codes=decision.reason_codes,
            decided_at=decision.decided_at,
            recorded_at=NOW,
        )
        self.pending.append(stored)
        return stored


class FakeUnitOfWork:
    def __init__(
        self,
        stored_candidate: StoredCandidate | None,
        evaluations: Sequence[StoredFilterEvaluation],
        *,
        failure_call: int | None = None,
        failure: PersistenceError | None = None,
    ) -> None:
        self.candidates = FakeCandidateRepository(stored_candidate)
        self.filter_evaluations = FakeFilterEvaluationRepository(evaluations)
        self.strategy_decisions = FakeStrategyDecisionRepository(
            failure_call=failure_call,
            failure=failure,
        )
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
        self.strategy_decisions.pending.clear()
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.finished:
            self.rollback()


@dataclass(frozen=True, slots=True)
class FakeUnitOfWorkFactory:
    unit_of_work: FakeUnitOfWork

    def __call__(self) -> FakeUnitOfWork:
        return self.unit_of_work


def service_with(
    evaluations: Sequence[StoredFilterEvaluation] | None = None,
    *,
    stored_candidate: StoredCandidate | None = None,
    candidate_present: bool = True,
    failure_call: int | None = None,
    failure: PersistenceError | None = None,
) -> tuple[
    CandidateStrategyDecisionService,
    FakeUnitOfWork,
    RecordingClock,
    FakeDecisionIDFactory,
]:
    unit_of_work = FakeUnitOfWork(
        candidate() if candidate_present and stored_candidate is None else stored_candidate,
        evaluation_batch() if evaluations is None else evaluations,
        failure_call=failure_call,
        failure=failure,
    )
    clock = RecordingClock()
    id_factory = FakeDecisionIDFactory()
    service = CandidateStrategyDecisionService(
        FakeUnitOfWorkFactory(unit_of_work),
        clock,
        id_factory,
    )
    return service, unit_of_work, clock, id_factory
