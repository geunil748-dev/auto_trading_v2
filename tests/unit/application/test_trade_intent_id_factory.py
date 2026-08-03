from uuid import UUID

from auto_trading_v2.adapters.identifiers import UuidTradeIntentIDFactory
from auto_trading_v2.domain.primitives import IdentifierFactory, TradeIntentID


def test_uuid_adapter_creates_only_a_typed_trade_intent_id() -> None:
    expected = UUID("11111111-1111-4111-8111-111111111111")
    factory = UuidTradeIntentIDFactory(IdentifierFactory(lambda: expected))

    created = factory.new()

    assert created == TradeIntentID(expected)
    assert type(created) is TradeIntentID
