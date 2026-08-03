from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.application.contracts.paper_fills import StoredPaperFill
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.persistence import StoredMarketSnapshot
from auto_trading_v2.application.contracts.position_projection import (
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
)
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
    PositionEventID,
    PositionID,
    Price,
    Quantity,
    SessionDate,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.strategy_decisions import StrategyAction
from auto_trading_v2.domain.strategy_decisions.catalog import STRICT_ENTRY
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide

NOW = datetime(2026, 7, 16, 12, tzinfo=UTC)
POSITION_ID = PositionID(UUID(int=1))
POSITION_EVENT_ID = PositionEventID(UUID(int=2))
FILL_ID = FillID(UUID(int=3))
ORDER_ID = OrderID(UUID(int=4))
TRADE_INTENT_ID = TradeIntentID(UUID(int=5))
ENTRY_DECISION_ID = DecisionID(UUID(int=6))
SNAPSHOT_ID = MarketSnapshotID(UUID(int=7))
EXIT_DECISION_ID = DecisionID(UUID(int=8))


def position(**changes: object) -> StoredPaperPosition:
    values: dict[str, object] = {
        "position_id": POSITION_ID,
        "strategy_id": STRICT_ENTRY.strategy_id,
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "status": PaperPositionStatus.OPEN,
        "quantity": Quantity(10),
        "average_cost_price": Price(Decimal("100")),
        "realized_pnl": Money(Decimal("0"), Currency("USD")),
        "opened_at": NOW - timedelta(hours=1),
        "closed_at": None,
        "version": 1,
        "updated_at": NOW - timedelta(minutes=1),
        "recorded_at": NOW - timedelta(hours=1),
    }
    values.update(changes)
    return StoredPaperPosition(**values)  # type: ignore[arg-type]


def event(**changes: object) -> StoredPositionEvent:
    values: dict[str, object] = {
        "position_event_id": POSITION_EVENT_ID,
        "position_id": POSITION_ID,
        "fill_id": FILL_ID,
        "sequence_no": 1,
        "event_type": PositionEventType.OPENED,
        "quantity_delta": Quantity(10),
        "quantity_after": Quantity(10),
        "average_cost_after": Price(Decimal("100")),
        "realized_pnl_delta": Money(Decimal("0"), Currency("USD")),
        "realized_pnl_after": Money(Decimal("0"), Currency("USD")),
        "occurred_at": NOW - timedelta(minutes=1),
        "recorded_at": NOW - timedelta(minutes=1),
    }
    values.update(changes)
    return StoredPositionEvent(**values)  # type: ignore[arg-type]


def fill() -> StoredPaperFill:
    return StoredPaperFill(
        fill_id=FILL_ID,
        order_id=ORDER_ID,
        execution_key="position-exit-source-fill",
        fill_sequence=1,
        quantity=Quantity(10),
        price=Price(Decimal("100")),
        fee=Money(Decimal("0"), Currency("USD")),
        executed_at=NOW - timedelta(minutes=1),
        recorded_at=NOW - timedelta(minutes=1),
    )


def order() -> StoredPaperOrder:
    return StoredPaperOrder(
        order_id=ORDER_ID,
        trade_intent_id=TRADE_INTENT_ID,
        client_order_id=ClientOrderID(UUID(int=9)),
        broker_code="INTERNAL_PAPER",
        broker_order_ref="position-exit-source-order",
        status=PaperOrderStatus.FILLED,
        rejection_code=None,
        submitted_at=NOW - timedelta(minutes=2),
        accepted_at=NOW - timedelta(minutes=2),
        closed_at=NOW - timedelta(minutes=1),
        version=2,
        updated_at=NOW - timedelta(minutes=1),
        recorded_at=NOW - timedelta(minutes=2),
    )


def intent(**changes: object) -> StoredTradeIntent:
    values: dict[str, object] = {
        "trade_intent_id": TRADE_INTENT_ID,
        "decision_id": ENTRY_DECISION_ID,
        "idempotency_key": "position-exit-source-intent",
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "side": TradeSide.BUY,
        "order_type": TradeOrderType.MARKET,
        "requested_quantity": Quantity(10),
        "limit_price": None,
        "time_in_force": TimeInForce.DAY,
        "created_at": NOW - timedelta(minutes=3),
        "recorded_at": NOW - timedelta(minutes=3),
    }
    values.update(changes)
    return StoredTradeIntent(**values)  # type: ignore[arg-type]


def entry_decision(**changes: object) -> StoredCandidateStrategyDecision:
    values: dict[str, object] = {
        "decision_id": ENTRY_DECISION_ID,
        "decision_key": "candidate:source|strategy:strict|version:v1",
        "candidate_id": CandidateID(UUID(int=10)),
        "filter_evaluation_id": FilterEvaluationID(UUID(int=11)),
        "strategy_id": STRICT_ENTRY.strategy_id,
        "strategy_version": "v1",
        "action": StrategyAction.ENTER_LONG,
        "reason_codes": ("ENTRY_ALLOWED",),
        "decided_at": NOW - timedelta(minutes=4),
        "recorded_at": NOW - timedelta(minutes=4),
    }
    values.update(changes)
    return StoredCandidateStrategyDecision(**values)  # type: ignore[arg-type]


def snapshot(**changes: object) -> StoredMarketSnapshot:
    price = Price(Decimal("100"))
    values: dict[str, object] = {
        "market_snapshot_id": SNAPSHOT_ID,
        "symbol": Symbol("AAPL"),
        "session_date": SessionDate(date(2026, 7, 16)),
        "observed_at": NOW,
        "source": "POSITION_EXIT_TEST",
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


def exit_decision() -> StoredPositionStrategyDecision:
    return StoredPositionStrategyDecision(
        decision_id=EXIT_DECISION_ID,
        decision_key="position:source|snapshot:source|strategy:strict|version:v1",
        position_id=POSITION_ID,
        position_version=1,
        market_snapshot_id=SNAPSHOT_ID,
        strategy_id=STRICT_ENTRY.strategy_id,
        strategy_version="v1",
        action=StrategyAction.SKIP,
        reason_codes=("EXIT_CONDITIONS_NOT_MET", "POSITION_HOLD"),
        decided_at=NOW,
        recorded_at=NOW,
    )
