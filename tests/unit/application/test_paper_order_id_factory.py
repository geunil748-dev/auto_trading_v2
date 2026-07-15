from uuid import NAMESPACE_URL, UUID, uuid5

from auto_trading_v2.adapters.identifiers import (
    Uuid5ClientOrderIDFactory,
    UuidOrderIDFactory,
)
from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    IdentifierFactory,
    OrderID,
    TradeIntentID,
)


def test_client_order_id_uses_exact_uuid5_name_contract() -> None:
    trade_intent_id = TradeIntentID(UUID("20000000-0000-0000-0000-000000000001"))
    expected_name = f"urn:auto-trading-v2:client-order:v1:{trade_intent_id.serialize()}"

    value = Uuid5ClientOrderIDFactory().for_trade_intent(trade_intent_id)

    assert value == ClientOrderID(uuid5(NAMESPACE_URL, expected_name))
    assert value == Uuid5ClientOrderIDFactory().for_trade_intent(trade_intent_id)
    assert value != Uuid5ClientOrderIDFactory().for_trade_intent(TradeIntentID(UUID(int=2)))


def test_order_id_factory_reuses_typed_identifier_factory() -> None:
    expected = UUID("30000000-0000-0000-0000-000000000001")
    factory = UuidOrderIDFactory(IdentifierFactory(lambda: expected))

    value = factory.new()

    assert value == OrderID(expected)
    assert not isinstance(value, ClientOrderID)
