from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    OptimisticConcurrencyError,
    PersistenceNotFoundError,
)
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    PositionEventID,
    PositionID,
    Price,
    Quantity,
)

from .paper_fill_fakes import (
    NOW,
    candidate,
    decision,
    fill,
    intent,
    order,
    snapshot,
)

POSITION_ID = PositionID(UUID(int=40))
POSITION_EVENT_ID = PositionEventID(UUID(int=41))
FILL_ID = FillID(UUID(int=21))


def position(**changes: object) -> StoredPaperPosition:
    values: dict[str, object] = {
        "position_id": POSITION_ID,
        "strategy_id": decision().strategy_id,
        "symbol": intent().symbol,
        "currency": Currency("USD"),
        "status": PaperPositionStatus.OPEN,
        "quantity": Quantity(10),
        "average_cost_price": Price(Decimal("100")),
        "realized_pnl": Money(Decimal("0"), Currency("USD")),
        "opened_at": NOW - timedelta(minutes=1),
        "closed_at": None,
        "version": 1,
        "updated_at": NOW,
        "recorded_at": NOW,
    }
    values.update(changes)
    return StoredPaperPosition(**values)  # type: ignore[arg-type]


def event(
    *,
    fill_id: FillID = FILL_ID,
    event_type: PositionEventType = PositionEventType.OPENED,
    sequence_no: int = 1,
    quantity_after: int = 10,
    average: str = "100",
) -> StoredPositionEvent:
    return StoredPositionEvent(
        position_event_id=POSITION_EVENT_ID,
        position_id=POSITION_ID,
        fill_id=fill_id,
        sequence_no=sequence_no,
        event_type=event_type,
        quantity_delta=Quantity(quantity_after),
        quantity_after=Quantity(quantity_after),
        average_cost_after=Price(Decimal(average)),
        realized_pnl_delta=Money(Decimal("0"), Currency("USD")),
        realized_pnl_after=Money(Decimal("0"), Currency("USD")),
        occurred_at=NOW,
        recorded_at=NOW,
    )


class ReadRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value
        self.calls = 0

    def get(self, identifier: object) -> object | None:
        self.calls += 1
        return self.value


class FakePositionRepository:
    def __init__(
        self,
        value: StoredPaperPosition | None,
        operations: list[str],
    ) -> None:
        self.value = value
        self.operations = operations
        self.add_calls: list[NewPaperPosition] = []
        self.transition_calls: list[PaperPositionBuyTransition] = []
        self.pending: StoredPaperPosition | None = None
        self.add_duplicate_constraint: str | None = None
        self.transition_failure: str | None = None

    def get_open_by_key(self, **kwargs: object) -> StoredPaperPosition | None:
        return self.value

    def add(self, value: NewPaperPosition) -> StoredPaperPosition:
        self.operations.append("position_add")
        self.add_calls.append(value)
        if self.add_duplicate_constraint is not None:
            raise DuplicateRecordError(
                entity="paper_position",
                operation="insert",
                constraint=self.add_duplicate_constraint,
            )
        stored = StoredPaperPosition(
            **{name: getattr(value, name) for name in value.__dataclass_fields__},
            recorded_at=NOW,
        )
        self.pending = stored
        return stored

    def transition_after_buy_fill(
        self,
        value: PaperPositionBuyTransition,
    ) -> StoredPaperPosition:
        self.operations.append("position_transition")
        self.transition_calls.append(value)
        if self.transition_failure == "stale":
            raise OptimisticConcurrencyError(
                entity="paper_position",
                operation="transition_after_buy_fill",
            )
        if self.transition_failure == "missing":
            raise PersistenceNotFoundError(
                entity="paper_position",
                operation="transition_after_buy_fill",
            )
        assert self.value is not None
        stored = replace(
            self.value,
            quantity=value.quantity,
            average_cost_price=value.average_cost_price,
            version=value.expected_version + 1,
            updated_at=value.updated_at,
        )
        self.pending = stored
        return stored

    def commit(self) -> None:
        if self.pending is not None:
            self.value = self.pending
        self.pending = None

    def rollback(self) -> None:
        self.pending = None


class FakeEventRepository:
    def __init__(
        self,
        existing: StoredPositionEvent | None,
        operations: list[str],
    ) -> None:
        self.existing = existing
        self.operations = operations
        self.add_calls: list[NewPositionEvent] = []
        self.pending: StoredPositionEvent | None = None
        self.duplicate_constraint: str | None = None

    def get_by_fill_id(self, fill_id: FillID) -> StoredPositionEvent | None:
        return (
            self.existing
            if self.existing is not None and self.existing.fill_id == fill_id
            else None
        )

    def add(self, value: NewPositionEvent) -> StoredPositionEvent:
        self.operations.append("event_add")
        self.add_calls.append(value)
        if self.duplicate_constraint is not None:
            raise DuplicateRecordError(
                entity="position_event",
                operation="insert",
                constraint=self.duplicate_constraint,
            )
        stored = StoredPositionEvent(
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
        fill_present: bool = True,
        missing_source: str | None = None,
        stored_fill: object | None = None,
        stored_order: object | None = None,
        stored_intent: object | None = None,
        stored_snapshot: object | None = None,
        stored_position: StoredPaperPosition | None = None,
        stored_event: StoredPositionEvent | None = None,
    ) -> None:
        self.operations: list[str] = []
        fill_value = fill() if stored_fill is None else stored_fill
        self.paper_fills = ReadRepository(fill_value if fill_present else None)
        order_value = order(PaperOrderStatus.PARTIALLY_FILLED, version=2)
        self.paper_orders = ReadRepository(
            None
            if missing_source == "order"
            else (order_value if stored_order is None else stored_order)
        )
        self.trade_intents = ReadRepository(
            None
            if missing_source == "intent"
            else (intent() if stored_intent is None else stored_intent)
        )
        self.strategy_decisions = ReadRepository(
            None if missing_source == "decision" else decision()
        )
        self.candidates = ReadRepository(None if missing_source == "candidate" else candidate())
        self.market_snapshots = ReadRepository(
            None
            if missing_source == "snapshot"
            else (snapshot() if stored_snapshot is None else stored_snapshot)
        )
        self.paper_positions = FakePositionRepository(stored_position, self.operations)
        self.position_events = FakeEventRepository(stored_event, self.operations)
        self.commit_calls = 0
        self.rollback_calls = 0
        self.finished = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1
        self.paper_positions.commit()
        self.position_events.commit()
        self.finished = True

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.paper_positions.rollback()
        self.position_events.rollback()
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
