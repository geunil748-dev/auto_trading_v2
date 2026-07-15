from uuid import UUID

from auto_trading_v2.adapters.identifiers.uuid_factory import UuidFillIDFactory
from auto_trading_v2.domain.primitives import FillID, IdentifierFactory, OrderID


def test_fill_id_factory_reuses_existing_typed_identifier_policy() -> None:
    expected = UUID("50000000-0000-0000-0000-000000000001")
    value = UuidFillIDFactory(IdentifierFactory(lambda: expected)).new()

    assert value == FillID(expected)
    assert not isinstance(value, OrderID)
