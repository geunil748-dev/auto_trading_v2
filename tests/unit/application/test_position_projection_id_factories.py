from uuid import UUID

from auto_trading_v2.adapters.identifiers import (
    UuidPositionEventIDFactory,
    UuidPositionIDFactory,
)
from auto_trading_v2.domain.primitives import IdentifierFactory, PositionEventID, PositionID


def test_position_factories_reuse_typed_identifier_policy() -> None:
    source = IdentifierFactory(lambda: UUID(int=10))

    position_id = UuidPositionIDFactory(source).new()
    event_id = UuidPositionEventIDFactory(source).new()

    assert isinstance(position_id, PositionID)
    assert isinstance(event_id, PositionEventID)
    assert type(position_id) is not type(event_id)
