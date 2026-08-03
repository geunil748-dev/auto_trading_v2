from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.adapters.brokers.internal_paper import (
    UNSUPPORTED_CURRENCY,
    UNSUPPORTED_ORDER_TYPE,
    UNSUPPORTED_SIDE,
    InternalPaperBroker,
)
from auto_trading_v2.application.contracts.paper_orders import PaperOrderSubmissionRequest
from auto_trading_v2.domain.paper_orders import PaperBrokerSubmissionOutcome
from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    Currency,
    Price,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide


def request() -> PaperOrderSubmissionRequest:
    return PaperOrderSubmissionRequest(
        trade_intent_id=TradeIntentID(UUID(int=1)),
        client_order_id=ClientOrderID(UUID(int=2)),
        symbol=Symbol("AAPL"),
        currency=Currency("USD"),
        side=TradeSide.BUY,
        order_type=TradeOrderType.MARKET,
        requested_quantity=Quantity(1),
        limit_price=None,
        time_in_force=TimeInForce.DAY,
        submitted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


def test_supported_request_is_accepted_deterministically() -> None:
    broker = InternalPaperBroker()
    value = request()

    first = broker.submit(value)
    second = broker.submit(value)

    assert first == second
    assert first.outcome is PaperBrokerSubmissionOutcome.ACCEPTED
    assert first.broker_code == "INTERNAL_PAPER"
    assert first.broker_order_ref == f"internal-paper:v1:{value.client_order_id}"
    assert first.processed_at == value.submitted_at
    assert first.rejection_code is None


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"currency": Currency("KRW")}, UNSUPPORTED_CURRENCY),
        ({"side": TradeSide.SELL}, UNSUPPORTED_SIDE),
        (
            {"order_type": TradeOrderType.LIMIT, "limit_price": Price(Decimal("1"))},
            UNSUPPORTED_ORDER_TYPE,
        ),
        (
            {
                "currency": Currency("KRW"),
                "side": TradeSide.SELL,
                "order_type": TradeOrderType.LIMIT,
                "limit_price": Price(Decimal("1")),
            },
            UNSUPPORTED_CURRENCY,
        ),
    ],
)
def test_unsupported_valid_requests_are_rejected_in_exact_priority(
    changes: dict[str, object], expected: str
) -> None:
    value = replace(request(), **changes)
    result = InternalPaperBroker().submit(value)

    assert result.outcome is PaperBrokerSubmissionOutcome.REJECTED
    assert result.rejection_code == expected
    assert result.broker_order_ref == f"internal-paper:v1:{value.client_order_id}"
