from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.paper_fills import NewPaperFill, StoredPaperFill
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    OrderID,
    Price,
    Quantity,
)

NOW = datetime(2026, 7, 16, 10, tzinfo=timezone(timedelta(hours=9)))
UTC_NOW = datetime(2026, 7, 16, 1, tzinfo=UTC)


def fill(**changes: object) -> NewPaperFill:
    values = {
        "fill_id": FillID(UUID(int=1)),
        "order_id": OrderID(UUID(int=2)),
        "execution_key": "order:test|fill-policy:internal-paper-split-fill|version:v1|sequence:1",
        "fill_sequence": 1,
        "quantity": Quantity(20),
        "price": Price(Decimal("25.123456789012345678")),
        "fee": Money(Decimal("0"), Currency("USD")),
        "executed_at": NOW,
    }
    values.update(changes)
    return NewPaperFill(**values)  # type: ignore[arg-type]


def test_new_and_stored_fill_are_typed_frozen_and_utc() -> None:
    value = fill()
    stored = StoredPaperFill(
        fill_id=value.fill_id,
        order_id=value.order_id,
        execution_key=value.execution_key,
        fill_sequence=value.fill_sequence,
        quantity=value.quantity,
        price=value.price,
        fee=value.fee,
        executed_at=value.executed_at,
        recorded_at=NOW,
    )

    assert value.executed_at == stored.recorded_at == UTC_NOW
    assert isinstance(value.fill_id, FillID)
    assert isinstance(value.order_id, OrderID)
    with pytest.raises(FrozenInstanceError):
        value.fill_sequence = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"execution_key": ""},
        {"execution_key": " padded "},
        {"execution_key": "X" * 161},
        {"fill_sequence": 0},
        {"fill_sequence": True},
        {"quantity": Quantity(0)},
        {"fee": Money(Decimal("-0.01"), Currency("USD"))},
        {"executed_at": datetime(2026, 7, 16)},
    ],
)
def test_invalid_fill_contract_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        fill(**changes)
