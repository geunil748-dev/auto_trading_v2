from datetime import UTC, datetime
from decimal import Decimal
from inspect import getmembers, isfunction
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.repositories.position_events import (
    SqlAlchemyPositionEventRepository,
    map_position_event,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.position_projection import PositionEventRepository
from auto_trading_v2.domain.position_projection import PositionEventType
from auto_trading_v2.domain.primitives import FillID, PositionEventID, PositionID

NOW = datetime(2026, 7, 16, 3, tzinfo=UTC)
SENTINEL = "SHOULD_NEVER_APPEAR_PR10_9f31c2"


def row(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "position_event_id": uuid4(),
        "position_id": uuid4(),
        "fill_id": uuid4(),
        "sequence_no": 1,
        "event_type": "OPENED",
        "quantity_delta": 10,
        "quantity_after": 10,
        "average_cost_after": Decimal("100.000000000000000000"),
        "realized_pnl_delta": Decimal("0E-18"),
        "realized_pnl_after": Decimal("0E-18"),
        "occurred_at": NOW,
        "recorded_at": NOW,
        "_position_currency": "USD",
    }
    values.update(changes)
    return values


def test_repository_protocol_has_append_and_identity_reads_only() -> None:
    methods = {
        name
        for name, value in getmembers(PositionEventRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {"add", "get", "get_by_fill_id"}
    assert not {"commit", "rollback", "update", "delete", "upsert"}.intersection(methods)


def test_event_row_maps_to_typed_contract_and_money_currency() -> None:
    mapped = map_position_event(row())

    assert isinstance(mapped.position_event_id, PositionEventID)
    assert isinstance(mapped.position_id, PositionID)
    assert isinstance(mapped.fill_id, FillID)
    assert mapped.event_type is PositionEventType.OPENED
    assert mapped.quantity_delta.value == mapped.quantity_after.value == 10
    assert mapped.average_cost_after.value == Decimal("100.000000000000000000")
    assert mapped.realized_pnl_delta.currency.code == "USD"


@pytest.mark.parametrize(
    "changes",
    [
        {"position_event_id": "invalid"},
        {"sequence_no": 0},
        {"event_type": "CLOSED"},
        {"quantity_delta": 0},
        {"quantity_after": -1},
        {"average_cost_after": Decimal("0")},
        {"occurred_at": datetime(2026, 7, 16, 3)},
        {"position_event_id": None, "_position_currency": SENTINEL},
    ],
)
def test_invalid_rows_are_safely_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(PersistenceMappingError) as captured:
        map_position_event(row(**changes))

    assert SENTINEL not in str(captured.value)
    assert SENTINEL not in repr(captured.value)


def test_repository_has_no_transaction_or_mutation_methods() -> None:
    names = set(dir(SqlAlchemyPositionEventRepository))
    assert not {"commit", "rollback", "begin", "update", "delete", "upsert"}.intersection(names)
