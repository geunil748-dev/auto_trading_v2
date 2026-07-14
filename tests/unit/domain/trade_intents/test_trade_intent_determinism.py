from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.domain.primitives import DecisionID, Price
from auto_trading_v2.domain.trade_intents import (
    plan_fixed_notional_quantity,
    trade_intent_idempotency_key,
)


def test_sizing_and_key_have_no_clock_or_random_input() -> None:
    price = Price(Decimal("29.123456789012345678"))
    decision_id = DecisionID(UUID(int=9))

    results = tuple(plan_fixed_notional_quantity(price) for _ in range(3))
    keys = tuple(trade_intent_idempotency_key(decision_id) for _ in range(3))

    assert results[0] == results[1] == results[2]
    assert keys[0] == keys[1] == keys[2]
    assert datetime.now(UTC).isoformat() not in keys[0]
