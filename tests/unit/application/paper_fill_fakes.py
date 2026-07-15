from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.paper_fills import (
    NewPaperFill,
    PaperOrderFillTransition,
    StoredPaperFill,
)
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.persistence import (
    StoredCandidate,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.errors import DuplicateRecordError, OptimisticConcurrencyError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import (
    CandidateID,
    ClientOrderID,
    Currency,
    DecisionID,
    FillID,
    FilterEvaluationID,
    MarketSnapshotID,
    Money,
    OrderID,
    Price,
    Quantity,
    RunID,
    SessionDate,
    StrategyID,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.strategy_decisions import StrategyAction
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide

NOW = datetime(2026, 7, 15, 3, tzinfo=UTC)
EXECUTED_AT = NOW + timedelta(minutes=1)
ORDER_ID = OrderID(UUID(int=1))
TRADE_INTENT_ID = TradeIntentID(UUID(int=2))
DECISION_ID = DecisionID(UUID(int=3))
CANDIDATE_ID = CandidateID(UUID(int=4))
SNAPSHOT_ID = MarketSnapshotID(UUID(int=5))


def intent(quantity: int = 40, **changes: object) -> StoredTradeIntent:
    values: dict[str, object] = {
        "trade_intent_id": TRADE_INTENT_ID,
        "decision_id": DECISION_ID,
        "idempotency_key": "decision:key|intent-policy:fixed-usd-notional|version:v1",
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "side": TradeSide.BUY,
        "order_type": TradeOrderType.MARKET,
        "requested_quantity": Quantity(quantity),
        "limit_price": None,
        "time_in_force": TimeInForce.DAY,
        "created_at": NOW,
        "recorded_at": NOW,
    }
    values.update(changes)
    return StoredTradeIntent(**values)  # type: ignore[arg-type]


def order(
    status: PaperOrderStatus = PaperOrderStatus.ACCEPTED,
    **changes: object,
) -> StoredPaperOrder:
    closed_statuses = {PaperOrderStatus.REJECTED, PaperOrderStatus.FILLED}
    closed = NOW if status in closed_statuses else None
    values: dict[str, object] = {
        "order_id": ORDER_ID,
        "trade_intent_id": TRADE_INTENT_ID,
        "client_order_id": ClientOrderID(UUID(int=6)),
        "broker_code": "INTERNAL_PAPER",
        "broker_order_ref": "internal-paper:v1:stable",
        "status": status,
        "rejection_code": "TEST_REJECTION" if status is PaperOrderStatus.REJECTED else None,
        "submitted_at": NOW,
        "accepted_at": None if status is PaperOrderStatus.REJECTED else NOW,
        "closed_at": closed,
        "version": 1,
        "updated_at": NOW,
        "recorded_at": NOW,
    }
    values.update(changes)
    return StoredPaperOrder(**values)  # type: ignore[arg-type]


def decision() -> StoredCandidateStrategyDecision:
    return StoredCandidateStrategyDecision(
        decision_id=DECISION_ID,
        decision_key="candidate:key|strategy:key|version:v1",
        candidate_id=CANDIDATE_ID,
        filter_evaluation_id=FilterEvaluationID(UUID(int=7)),
        strategy_id=StrategyID(UUID(int=8)),
        strategy_version="v1",
        action=StrategyAction.ENTER_LONG,
        reason_codes=("ENTRY_ALLOWED",),
        decided_at=NOW,
        recorded_at=NOW,
    )


def candidate() -> StoredCandidate:
    return StoredCandidate(
        candidate_id=CANDIDATE_ID,
        run_id=RunID(UUID(int=9)),
        market_snapshot_id=SNAPSHOT_ID,
        candidate_source="UNIT_TEST",
        rank=1,
        source_score=None,
        selected_at=NOW,
        recorded_at=NOW,
    )


def snapshot(**changes: object) -> StoredMarketSnapshot:
    price = Price(Decimal("25"))
    values: dict[str, object] = {
        "market_snapshot_id": SNAPSHOT_ID,
        "symbol": Symbol("AAPL"),
        "session_date": SessionDate(date(2026, 7, 15)),
        "observed_at": NOW,
        "source": "UNIT_TEST",
        "open_price": price,
        "high_price": price,
        "low_price": price,
        "last_price": price,
        "previous_high_price": price,
        "previous_low_price": price,
        "previous_close_price": price,
        "volume": 1,
        "recorded_at": NOW,
    }
    values.update(changes)
    return StoredMarketSnapshot(**values)  # type: ignore[arg-type]


def fill(sequence: int = 1, quantity: int = 20) -> StoredPaperFill:
    return StoredPaperFill(
        fill_id=FillID(UUID(int=20 + sequence)),
        order_id=ORDER_ID,
        execution_key=(
            f"order:{ORDER_ID}|fill-policy:internal-paper-split-fill|version:v1|sequence:{sequence}"
        ),
        fill_sequence=sequence,
        quantity=Quantity(quantity),
        price=Price(Decimal("25")),
        fee=Money(Decimal("0"), Currency("USD")),
        executed_at=NOW,
        recorded_at=NOW,
    )


class ReadRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value
        self.calls = 0

    def get(self, identifier: object) -> object | None:
        self.calls += 1
        return self.value


class FakeFillRepository:
    def __init__(self, fills: Sequence[StoredPaperFill] = ()) -> None:
        self.fills = tuple(fills)
        self.add_calls: list[NewPaperFill] = []
        self.duplicate = False

    def list_by_order(self, order_id: OrderID) -> Sequence[StoredPaperFill]:
        return self.fills

    def add(self, value: NewPaperFill) -> StoredPaperFill:
        self.add_calls.append(value)
        if self.duplicate:
            raise DuplicateRecordError(entity="paper_fill", operation="insert")
        return StoredPaperFill(
            **{name: getattr(value, name) for name in value.__dataclass_fields__},
            recorded_at=EXECUTED_AT,
        )


class FakeOrderRepository(ReadRepository):
    def __init__(self, value: StoredPaperOrder | None) -> None:
        super().__init__(value)
        self.transition_calls: list[PaperOrderFillTransition] = []
        self.stale = False

    def transition_after_fill(self, value: PaperOrderFillTransition) -> StoredPaperOrder:
        self.transition_calls.append(value)
        if self.stale:
            raise OptimisticConcurrencyError(
                entity="paper_order",
                operation="transition_after_fill",
            )
        assert isinstance(self.value, StoredPaperOrder)
        return replace(
            self.value,
            status=value.new_status,
            closed_at=value.closed_at,
            version=value.expected_version + 1,
            updated_at=value.updated_at,
        )


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        order_present: bool = True,
        missing_source: str | None = None,
        stored_order: StoredPaperOrder | None = None,
        stored_intent: StoredTradeIntent | None = None,
        stored_decision: StoredCandidateStrategyDecision | None = None,
        stored_candidate: StoredCandidate | None = None,
        stored_snapshot: StoredMarketSnapshot | None = None,
        fills: Sequence[StoredPaperFill] = (),
    ) -> None:
        self.paper_orders = FakeOrderRepository(
            (order() if stored_order is None else stored_order) if order_present else None
        )
        self.trade_intents = ReadRepository(
            None
            if missing_source == "intent"
            else (intent() if stored_intent is None else stored_intent)
        )
        self.strategy_decisions = ReadRepository(
            None
            if missing_source == "decision"
            else (decision() if stored_decision is None else stored_decision)
        )
        self.candidates = ReadRepository(
            None
            if missing_source == "candidate"
            else (candidate() if stored_candidate is None else stored_candidate)
        )
        self.market_snapshots = ReadRepository(
            None
            if missing_source == "snapshot"
            else (snapshot() if stored_snapshot is None else stored_snapshot)
        )
        self.paper_fills = FakeFillRepository(fills)
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
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.finished:
            self.rollback()


class CountingClock:
    def __init__(self) -> None:
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return EXECUTED_AT


class CountingFillIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> FillID:
        self.calls += 1
        return FillID(UUID(int=30))
