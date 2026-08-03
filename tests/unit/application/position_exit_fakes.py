from __future__ import annotations

from datetime import datetime
from types import TracebackType

from auto_trading_v2.application.contracts.paper_fills import StoredPaperFill
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.persistence import StoredMarketSnapshot
from auto_trading_v2.application.contracts.position_projection import (
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewPositionStrategyDecision,
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.services.position_exit_decision import (
    PositionExitDecisionService,
)
from auto_trading_v2.domain.primitives import DecisionID, PositionID

from .position_exit_records import (
    EXIT_DECISION_ID,
    NOW,
    entry_decision,
    event,
    fill,
    intent,
    order,
    position,
    snapshot,
)


class ReadRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value
        self.calls = 0

    def get(self, identifier: object) -> object | None:
        self.calls += 1
        return self.value


class EventRepository:
    def __init__(self, value: StoredPositionEvent | None) -> None:
        self.value = value
        self.calls: list[tuple[PositionID, int]] = []

    def get_by_position_sequence(
        self,
        position_id: PositionID,
        sequence_no: int,
    ) -> StoredPositionEvent | None:
        self.calls.append((position_id, sequence_no))
        return self.value


class DecisionRepository:
    def __init__(
        self,
        entry: StoredCandidateStrategyDecision,
        existing: StoredPositionStrategyDecision | None,
    ) -> None:
        self.entry = entry
        self.existing = existing
        self.add_calls: list[NewPositionStrategyDecision] = []
        self.pending: StoredPositionStrategyDecision | None = None
        self.duplicate_constraint: str | None = None

    def get(self, decision_id: DecisionID) -> StoredCandidateStrategyDecision | None:
        return self.entry if decision_id == self.entry.decision_id else None

    def get_by_position_snapshot_strategy(self, **values: object):
        return self.existing

    def add_position(
        self,
        value: NewPositionStrategyDecision,
    ) -> StoredPositionStrategyDecision:
        self.add_calls.append(value)
        if self.duplicate_constraint is not None:
            raise DuplicateRecordError(
                entity="strategy_decision",
                operation="insert",
                constraint=self.duplicate_constraint,
            )
        stored = StoredPositionStrategyDecision(
            **{name: getattr(value, name) for name in value.__dataclass_fields__},
            recorded_at=NOW,
        )
        self.pending = stored
        return stored

    def commit(self) -> None:
        if self.pending is not None:
            self.existing = self.pending
        self.pending = None

    def rollback(self) -> None:
        self.pending = None


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        stored_position: StoredPaperPosition | None = None,
        stored_event: StoredPositionEvent | None = None,
        stored_fill: StoredPaperFill | None = None,
        stored_order: StoredPaperOrder | None = None,
        stored_intent: StoredTradeIntent | None = None,
        stored_entry_decision: StoredCandidateStrategyDecision | None = None,
        stored_snapshot: StoredMarketSnapshot | None = None,
        existing_exit: StoredPositionStrategyDecision | None = None,
    ) -> None:
        self.paper_positions = ReadRepository(
            position() if stored_position is None else stored_position
        )
        self.position_events = EventRepository(event() if stored_event is None else stored_event)
        self.paper_fills = ReadRepository(fill() if stored_fill is None else stored_fill)
        self.paper_orders = ReadRepository(order() if stored_order is None else stored_order)
        self.trade_intents = ReadRepository(intent() if stored_intent is None else stored_intent)
        source_decision = (
            entry_decision() if stored_entry_decision is None else stored_entry_decision
        )
        self.strategy_decisions = DecisionRepository(source_decision, existing_exit)
        self.market_snapshots = ReadRepository(
            snapshot() if stored_snapshot is None else stored_snapshot
        )
        self.commit_calls = 0
        self.rollback_calls = 0
        self.finished = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1
        self.strategy_decisions.commit()
        self.finished = True

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.strategy_decisions.rollback()
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.finished:
            self.rollback()


class FakeUnitOfWorkFactory:
    def __init__(self, *unit_of_works: FakeUnitOfWork) -> None:
        self.unit_of_works = list(unit_of_works)
        self.calls = 0

    def __call__(self) -> FakeUnitOfWork:
        value = self.unit_of_works[min(self.calls, len(self.unit_of_works) - 1)]
        self.calls += 1
        return value


class CountingClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return self.now


class CountingDecisionIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> DecisionID:
        self.calls += 1
        return EXIT_DECISION_ID


def service_for(
    *unit_of_works: FakeUnitOfWork,
    now: datetime = NOW,
) -> tuple[
    PositionExitDecisionService,
    FakeUnitOfWorkFactory,
    CountingClock,
    CountingDecisionIDFactory,
]:
    factory = FakeUnitOfWorkFactory(*unit_of_works)
    clock = CountingClock(now)
    ids = CountingDecisionIDFactory()
    return PositionExitDecisionService(factory, clock, ids), factory, clock, ids


def assert_no_write(unit_of_work: FakeUnitOfWork, ids: CountingDecisionIDFactory) -> None:
    assert unit_of_work.strategy_decisions.add_calls == []
    assert unit_of_work.commit_calls == 0
    assert ids.calls == 0
