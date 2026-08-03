from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
    PositionProjectionResult,
    StoredPaperPosition,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
    ProjectionOutcome,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    Money,
    PositionEventID,
    PositionID,
    Price,
    Quantity,
    StrategyID,
    Symbol,
)

NOW = datetime(2026, 7, 16, 12, tzinfo=timezone(timedelta(hours=9)))
UTC_NOW = datetime(2026, 7, 16, 3, tzinfo=UTC)


def new_position(**changes: object) -> NewPaperPosition:
    values: dict[str, object] = {
        "position_id": PositionID(UUID(int=1)),
        "strategy_id": StrategyID(UUID(int=2)),
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "status": PaperPositionStatus.OPEN,
        "quantity": Quantity(10),
        "average_cost_price": Price(Decimal("100")),
        "realized_pnl": Money(Decimal("0"), Currency("USD")),
        "opened_at": NOW,
        "closed_at": None,
        "version": 1,
        "updated_at": NOW,
    }
    values.update(changes)
    return NewPaperPosition(**values)  # type: ignore[arg-type]


def new_event(**changes: object) -> NewPositionEvent:
    values: dict[str, object] = {
        "position_event_id": PositionEventID(UUID(int=3)),
        "position_id": PositionID(UUID(int=1)),
        "fill_id": FillID(UUID(int=4)),
        "sequence_no": 1,
        "event_type": PositionEventType.OPENED,
        "quantity_delta": Quantity(10),
        "quantity_after": Quantity(10),
        "average_cost_after": Price(Decimal("100")),
        "realized_pnl_delta": Money(Decimal("0"), Currency("USD")),
        "realized_pnl_after": Money(Decimal("0"), Currency("USD")),
        "occurred_at": NOW,
    }
    values.update(changes)
    return NewPositionEvent(**values)  # type: ignore[arg-type]


def test_position_contract_is_frozen_typed_and_utc() -> None:
    value = new_position()
    stored = StoredPaperPosition(
        **{name: getattr(value, name) for name in value.__dataclass_fields__},
        recorded_at=NOW,
    )

    assert value.opened_at == value.updated_at == stored.recorded_at == UTC_NOW
    assert stored.status is PaperPositionStatus.OPEN
    with pytest.raises(FrozenInstanceError):
        value.version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"status": PaperPositionStatus.CLOSED},
        {"quantity": Quantity(0)},
        {"closed_at": NOW},
        {"version": 2},
        {"realized_pnl": Money(Decimal("1"), Currency("USD"))},
        {"updated_at": NOW + timedelta(seconds=1)},
    ],
)
def test_new_position_requires_exact_opened_state(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        new_position(**changes)


def test_buy_transition_normalizes_time_and_rejects_version_zero() -> None:
    transition = PaperPositionBuyTransition(
        position_id=PositionID(UUID(int=1)),
        expected_version=1,
        quantity=Quantity(15),
        average_cost_price=Price(Decimal("110")),
        updated_at=NOW,
    )

    assert transition.updated_at == UTC_NOW
    with pytest.raises(ValidationError):
        replace(transition, expected_version=0)


def test_event_and_result_are_typed_immutable_buy_facts() -> None:
    event = new_event()
    result = PositionProjectionResult(
        outcome=ProjectionOutcome.APPLIED,
        fill_id=event.fill_id,
        position_id=event.position_id,
        position_event_id=event.position_event_id,
        event_type=event.event_type,
        quantity=event.quantity_after,
        average_cost_price=event.average_cost_after,
        position_version=event.sequence_no,
    )

    assert event.occurred_at == UTC_NOW
    assert result.event_type is PositionEventType.OPENED
    with pytest.raises(FrozenInstanceError):
        result.position_version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"sequence_no": 0},
        {"quantity_delta": Quantity(0)},
        {"quantity_after": Quantity(5)},
        {"realized_pnl_delta": Money(Decimal("1"), Currency("USD"))},
        {"occurred_at": datetime(2026, 7, 16, 3)},
    ],
)
def test_invalid_position_event_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        new_event(**changes)
