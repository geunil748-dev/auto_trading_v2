from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.paper_orders import (
    NewPaperOrder,
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
    StoredPaperOrder,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.ports.paper_broker import PaperBrokerError
from auto_trading_v2.domain.paper_orders import PaperBrokerSubmissionOutcome, PaperOrderStatus
from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    Currency,
    DecisionID,
    OrderID,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide

NOW = datetime(2026, 7, 15, 1, tzinfo=UTC)
TRADE_INTENT_ID = TradeIntentID(UUID(int=1))
CLIENT_ORDER_ID = ClientOrderID(UUID(int=2))
ORDER_ID = OrderID(UUID(int=3))


def stored_trade_intent(**changes: object) -> StoredTradeIntent:
    values = {
        "trade_intent_id": TRADE_INTENT_ID,
        "decision_id": DecisionID(UUID(int=4)),
        "idempotency_key": "decision:key|intent-policy:fixed-usd-notional|version:v1",
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "side": TradeSide.BUY,
        "order_type": TradeOrderType.MARKET,
        "requested_quantity": Quantity(40),
        "limit_price": None,
        "time_in_force": TimeInForce.DAY,
        "created_at": NOW,
        "recorded_at": NOW,
    }
    values.update(changes)
    return StoredTradeIntent(**values)  # type: ignore[arg-type]


def broker_result(
    outcome: PaperBrokerSubmissionOutcome = PaperBrokerSubmissionOutcome.ACCEPTED,
) -> PaperOrderSubmissionResult:
    accepted = outcome is PaperBrokerSubmissionOutcome.ACCEPTED
    return PaperOrderSubmissionResult(
        outcome=outcome,
        broker_code="INTERNAL_PAPER",
        broker_order_ref=f"internal-paper:v1:{CLIENT_ORDER_ID}",
        processed_at=NOW,
        rejection_code=None if accepted else "UNSUPPORTED_SIDE",
    )


def stored_order(new: NewPaperOrder | None = None) -> StoredPaperOrder:
    source = new or NewPaperOrder(
        order_id=ORDER_ID,
        trade_intent_id=TRADE_INTENT_ID,
        client_order_id=CLIENT_ORDER_ID,
        broker_code="INTERNAL_PAPER",
        broker_order_ref=f"internal-paper:v1:{CLIENT_ORDER_ID}",
        status=PaperOrderStatus.ACCEPTED,
        rejection_code=None,
        submitted_at=NOW,
        accepted_at=NOW,
        closed_at=None,
        version=1,
        updated_at=NOW,
    )
    return StoredPaperOrder(
        order_id=source.order_id,
        trade_intent_id=source.trade_intent_id,
        client_order_id=source.client_order_id,
        broker_code=source.broker_code,
        broker_order_ref=source.broker_order_ref,
        status=source.status,
        rejection_code=source.rejection_code,
        submitted_at=source.submitted_at,
        accepted_at=source.accepted_at,
        closed_at=source.closed_at,
        version=source.version,
        updated_at=source.updated_at,
        recorded_at=NOW,
    )


class FakeTradeIntentRepository:
    def __init__(self, value: StoredTradeIntent | None) -> None:
        self.value = value
        self.get_calls = 0

    def get(self, trade_intent_id: TradeIntentID) -> StoredTradeIntent | None:
        self.get_calls += 1
        return self.value if trade_intent_id == TRADE_INTENT_ID else None


class FakePaperOrderRepository:
    def __init__(self) -> None:
        self.by_trade_intent: StoredPaperOrder | None = None
        self.by_client: StoredPaperOrder | None = None
        self.by_reference: StoredPaperOrder | None = None
        self.add_calls: list[NewPaperOrder] = []
        self.fail_duplicate = False

    def get_by_trade_intent(self, trade_intent_id: TradeIntentID) -> StoredPaperOrder | None:
        return self.by_trade_intent

    def get_by_client_order_id(self, client_order_id: ClientOrderID) -> StoredPaperOrder | None:
        return self.by_client

    def get_by_broker_reference(
        self, *, broker_code: str, broker_order_ref: str
    ) -> StoredPaperOrder | None:
        return self.by_reference

    def add(self, value: NewPaperOrder) -> StoredPaperOrder:
        self.add_calls.append(value)
        if self.fail_duplicate:
            raise DuplicateRecordError(entity="paper_order", operation="insert")
        return stored_order(value)


class FakeUnitOfWork:
    def __init__(self, intent: StoredTradeIntent | None) -> None:
        self.trade_intents = FakeTradeIntentRepository(intent)
        self.paper_orders = FakePaperOrderRepository()
        self.commit_calls = 0
        self.rollback_calls = 0

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeUnitOfWorkFactory:
    def __init__(self, unit_of_work: FakeUnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    def __call__(self) -> FakeUnitOfWork:
        return self.unit_of_work


class CountingClock:
    def __init__(self) -> None:
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return NOW


class FakeClientOrderIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def for_trade_intent(self, trade_intent_id: TradeIntentID) -> ClientOrderID:
        self.calls += 1
        return CLIENT_ORDER_ID


class FakeOrderIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> OrderID:
        self.calls += 1
        return ORDER_ID


class FakeBroker:
    broker_code = "INTERNAL_PAPER"

    def __init__(self, result: object | None = None, *, fail: bool = False) -> None:
        self.result = broker_result() if result is None else result
        self.fail = fail
        self.calls: list[PaperOrderSubmissionRequest] = []

    def submit(self, request: PaperOrderSubmissionRequest) -> PaperOrderSubmissionResult:
        self.calls.append(request)
        if self.fail:
            raise PaperBrokerError("adapter_unavailable")
        return self.result  # type: ignore[return-value]
