from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.persistence import (
    StoredCandidate,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.services.trade_intent import CandidateTradeIntentService
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    MarketSnapshotID,
    Price,
    RunID,
    SessionDate,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction

NOW = datetime(2026, 7, 14, 7, tzinfo=UTC)
CANDIDATE_ID = CandidateID(UUID(int=1))
SNAPSHOT_ID = MarketSnapshotID(UUID(int=2))


def candidate() -> StoredCandidate:
    return StoredCandidate(
        candidate_id=CANDIDATE_ID,
        run_id=RunID(UUID(int=3)),
        market_snapshot_id=SNAPSHOT_ID,
        candidate_source="UNIT_TEST",
        rank=1,
        source_score=None,
        selected_at=NOW,
        recorded_at=NOW,
    )


def snapshot(price: str = "25") -> StoredMarketSnapshot:
    value = Price(Decimal(price))
    return StoredMarketSnapshot(
        market_snapshot_id=SNAPSHOT_ID,
        symbol=Symbol("AAPL"),
        session_date=SessionDate(date(2026, 7, 14)),
        observed_at=NOW,
        source="UNIT_TEST",
        open_price=value,
        high_price=value,
        low_price=value,
        last_price=value,
        previous_high_price=value,
        previous_low_price=value,
        previous_close_price=value,
        volume=1,
        recorded_at=NOW,
    )


def decision_batch(
    actions: Sequence[StrategyAction],
) -> list[StoredCandidateStrategyDecision]:
    return [
        StoredCandidateStrategyDecision(
            decision_id=DecisionID(UUID(int=100 + index)),
            decision_key=f"decision-{index}",
            candidate_id=CANDIDATE_ID,
            filter_evaluation_id=FilterEvaluationID(UUID(int=200 + index)),
            strategy_id=definition.strategy_id,
            strategy_version=definition.strategy_version,
            action=action,
            reason_codes=("TEST",),
            decided_at=NOW,
            recorded_at=NOW,
        )
        for index, (definition, action) in enumerate(zip(BUILT_IN_STRATEGIES, actions, strict=True))
    ]


class RecordingClock:
    def __init__(self) -> None:
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return NOW


class FakeTradeIntentIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> TradeIntentID:
        result = TradeIntentID(UUID(int=300 + self.calls))
        self.calls += 1
        return result


class FakeCandidateRepository:
    def __init__(self, stored: StoredCandidate | None) -> None:
        self.stored = stored

    def get(self, candidate_id: CandidateID) -> StoredCandidate | None:
        return self.stored if candidate_id == CANDIDATE_ID else None


class FakeSnapshotRepository:
    def __init__(self, stored: StoredMarketSnapshot | None) -> None:
        self.stored = stored

    def get(self, snapshot_id: MarketSnapshotID) -> StoredMarketSnapshot | None:
        return self.stored if snapshot_id == SNAPSHOT_ID else None


class FakeDecisionRepository:
    def __init__(self, decisions: Sequence[StoredCandidateStrategyDecision]) -> None:
        self.decisions = tuple(decisions)

    def list_by_candidate(
        self,
        candidate_id: CandidateID,
    ) -> Sequence[StoredCandidateStrategyDecision]:
        return self.decisions


class FakeTradeIntentRepository:
    def __init__(self, failure_call: int | None = None) -> None:
        self.failure_call = failure_call
        self.add_calls: list[NewTradeIntent] = []
        self.pending: list[StoredTradeIntent] = []

    def add(self, trade_intent: NewTradeIntent) -> StoredTradeIntent:
        self.add_calls.append(trade_intent)
        if self.failure_call == len(self.add_calls):
            raise DuplicateRecordError(
                entity="trade_intent",
                operation="insert",
                reason="duplicate_record",
            )
        stored = StoredTradeIntent(
            **{name: getattr(trade_intent, name) for name in trade_intent.__dataclass_fields__},
            recorded_at=NOW,
        )
        self.pending.append(stored)
        return stored


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        stored_candidate: StoredCandidate | None,
        stored_snapshot: StoredMarketSnapshot | None,
        decisions: Sequence[StoredCandidateStrategyDecision],
        failure_call: int | None = None,
    ) -> None:
        self.candidates = FakeCandidateRepository(stored_candidate)
        self.market_snapshots = FakeSnapshotRepository(stored_snapshot)
        self.strategy_decisions = FakeDecisionRepository(decisions)
        self.trade_intents = FakeTradeIntentRepository(failure_call)
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
        self.trade_intents.pending.clear()
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
    actions: Sequence[StrategyAction],
    *,
    stored_candidate: StoredCandidate | None = None,
    stored_snapshot: StoredMarketSnapshot | None = None,
    decisions: Sequence[StoredCandidateStrategyDecision] | None = None,
    failure_call: int | None = None,
) -> tuple[CandidateTradeIntentService, FakeUnitOfWork, RecordingClock, FakeTradeIntentIDFactory]:
    unit_of_work = FakeUnitOfWork(
        stored_candidate=candidate() if stored_candidate is None else stored_candidate,
        stored_snapshot=snapshot() if stored_snapshot is None else stored_snapshot,
        decisions=decision_batch(actions) if decisions is None else decisions,
        failure_call=failure_call,
    )
    clock = RecordingClock()
    id_factory = FakeTradeIntentIDFactory()
    service = CandidateTradeIntentService(FakeUnitOfWorkFactory(unit_of_work), clock, id_factory)
    return service, unit_of_work, clock, id_factory
