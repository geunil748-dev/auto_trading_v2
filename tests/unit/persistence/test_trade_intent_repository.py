from datetime import UTC, datetime
from decimal import Decimal
from inspect import getmembers, isfunction
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.repositories.trade_intents import (
    SqlAlchemyTradeIntentRepository,
    map_trade_intent,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.trade_intents import TradeIntentRepository
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide

SENTINEL = "SHOULD_NEVER_APPEAR_PR7_782c1f"


def row(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "trade_intent_id": uuid4(),
        "decision_id": uuid4(),
        "idempotency_key": "decision:key|intent-policy:fixed-usd-notional|version:v1",
        "symbol": "AAPL",
        "currency": "USD",
        "side": "BUY",
        "order_type": "MARKET",
        "requested_quantity": 40,
        "limit_price": None,
        "time_in_force": "DAY",
        "created_at": datetime(2026, 7, 14, 6, tzinfo=UTC),
        "recorded_at": datetime(2026, 7, 14, 6, 1, tzinfo=UTC),
    }
    values.update(changes)
    return values


def test_repository_protocol_has_only_required_add_and_reads() -> None:
    methods = {
        name
        for name, value in getmembers(TradeIntentRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {"add", "get", "get_by_decision", "get_by_idempotency_key"}
    assert not {"commit", "rollback", "update", "delete", "upsert"}.intersection(methods)


def test_market_and_limit_rows_map_to_typed_contracts() -> None:
    market = map_trade_intent(row())
    limit = map_trade_intent(row(order_type="LIMIT", limit_price=Decimal("25.125000000000000000")))

    assert market.side is TradeSide.BUY
    assert market.order_type is TradeOrderType.MARKET
    assert market.time_in_force is TimeInForce.DAY
    assert market.requested_quantity.value == 40
    assert market.limit_price is None
    assert limit.order_type is TradeOrderType.LIMIT
    assert limit.limit_price is not None
    assert limit.limit_price.value == Decimal("25.125000000000000000")


@pytest.mark.parametrize(
    "changes",
    [
        {"side": "HOLD"},
        {"order_type": "STOP"},
        {"requested_quantity": 0},
        {"created_at": datetime(2026, 7, 14)},
        {"order_type": "MARKET", "limit_price": Decimal("1")},
        {"order_type": "LIMIT", "limit_price": None},
        {"trade_intent_id": None, "idempotency_key": SENTINEL},
    ],
)
def test_invalid_row_is_safely_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(PersistenceMappingError) as captured:
        map_trade_intent(row(**changes))

    assert SENTINEL not in str(captured.value)
    assert SENTINEL not in repr(captured.value)


def test_repository_owns_no_transaction_or_mutation_methods() -> None:
    names = set(dir(SqlAlchemyTradeIntentRepository))

    assert not {"commit", "rollback", "begin", "update", "delete", "upsert"}.intersection(names)
