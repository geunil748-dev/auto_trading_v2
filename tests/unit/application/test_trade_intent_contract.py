from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    Currency,
    DecisionID,
    Price,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide


def intent(**changes: object) -> NewTradeIntent:
    values: dict[str, object] = {
        "trade_intent_id": TradeIntentID(UUID(int=1)),
        "decision_id": DecisionID(UUID(int=2)),
        "idempotency_key": "decision:key|intent-policy:fixed-usd-notional|version:v1",
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "side": TradeSide.BUY,
        "order_type": TradeOrderType.MARKET,
        "requested_quantity": Quantity(3),
        "limit_price": None,
        "time_in_force": TimeInForce.DAY,
        "created_at": datetime(2026, 7, 14, 15, tzinfo=timezone(timedelta(hours=9))),
    }
    values.update(changes)
    return NewTradeIntent(**values)  # type: ignore[arg-type]


def test_contract_is_typed_frozen_and_normalizes_utc() -> None:
    new = intent()
    stored = StoredTradeIntent(
        **{field.name: getattr(new, field.name) for field in fields(new)},
        recorded_at=datetime(2026, 7, 14, 6, 1, tzinfo=UTC),
    )

    assert isinstance(new.trade_intent_id, TradeIntentID)
    assert isinstance(new.decision_id, DecisionID)
    assert new.created_at == datetime(2026, 7, 14, 6, tzinfo=UTC)
    assert stored.recorded_at.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        new.idempotency_key = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("key", ["", " leading", "has space", "x" * 161])
def test_contract_rejects_invalid_idempotency_key(key: str) -> None:
    with pytest.raises(ValidationError):
        intent(idempotency_key=key)


def test_contract_rejects_zero_quantity_and_naive_time() -> None:
    with pytest.raises(ValidationError):
        intent(requested_quantity=Quantity(0))
    with pytest.raises(ValidationError):
        intent(created_at=datetime(2026, 7, 14))


def test_market_and_limit_price_shapes_are_exact() -> None:
    assert intent(order_type=TradeOrderType.MARKET, limit_price=None).limit_price is None
    limit = intent(
        order_type=TradeOrderType.LIMIT,
        limit_price=Price(Decimal("25.5")),
    )
    assert limit.limit_price == Price(Decimal("25.5"))
    with pytest.raises(ValidationError):
        intent(order_type=TradeOrderType.MARKET, limit_price=Price(Decimal("1")))
    with pytest.raises(ValidationError):
        intent(order_type=TradeOrderType.LIMIT, limit_price=None)
