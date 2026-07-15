from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.paper_orders import (
    NewPaperOrder,
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
    StoredPaperOrder,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.paper_orders import (
    PaperBrokerSubmissionOutcome,
    PaperOrderStatus,
)
from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    Currency,
    OrderID,
    Price,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide

NOW = datetime(2026, 7, 15, 10, tzinfo=timezone(timedelta(hours=9)))
UTC_NOW = datetime(2026, 7, 15, 1, tzinfo=UTC)


def request(**changes: object) -> PaperOrderSubmissionRequest:
    values = {
        "trade_intent_id": TradeIntentID(UUID(int=1)),
        "client_order_id": ClientOrderID(UUID(int=2)),
        "symbol": Symbol("AAPL"),
        "currency": Currency("USD"),
        "side": TradeSide.BUY,
        "order_type": TradeOrderType.MARKET,
        "requested_quantity": Quantity(2),
        "limit_price": None,
        "time_in_force": TimeInForce.DAY,
        "submitted_at": NOW,
    }
    values.update(changes)
    return PaperOrderSubmissionRequest(**values)  # type: ignore[arg-type]


def order(**changes: object) -> NewPaperOrder:
    values = {
        "order_id": OrderID(UUID(int=3)),
        "trade_intent_id": TradeIntentID(UUID(int=1)),
        "client_order_id": ClientOrderID(UUID(int=2)),
        "broker_code": "INTERNAL_PAPER",
        "broker_order_ref": "internal-paper:v1:reference",
        "status": PaperOrderStatus.ACCEPTED,
        "rejection_code": None,
        "submitted_at": UTC_NOW,
        "accepted_at": UTC_NOW,
        "closed_at": None,
        "version": 1,
        "updated_at": UTC_NOW,
    }
    values.update(changes)
    return NewPaperOrder(**values)  # type: ignore[arg-type]


def test_request_is_typed_frozen_and_normalized_to_utc() -> None:
    value = request()

    assert value.submitted_at == UTC_NOW
    with pytest.raises(FrozenInstanceError):
        value.symbol = Symbol("MSFT")  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_quantity": Quantity(0)},
        {"submitted_at": datetime(2026, 7, 15)},
        {"limit_price": Price(Decimal("1"))},
        {"order_type": TradeOrderType.LIMIT, "limit_price": None},
    ],
)
def test_invalid_request_shapes_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(**changes)


def test_limit_request_requires_and_preserves_positive_price() -> None:
    value = request(order_type=TradeOrderType.LIMIT, limit_price=Price(Decimal("1.25")))
    assert value.limit_price == Price(Decimal("1.25"))


def test_result_contract_accepts_valid_accepted_and_rejected_shapes() -> None:
    accepted = PaperOrderSubmissionResult(
        PaperBrokerSubmissionOutcome.ACCEPTED,
        "INTERNAL_PAPER",
        "reference",
        NOW,
        None,
    )
    rejected = PaperOrderSubmissionResult(
        PaperBrokerSubmissionOutcome.REJECTED,
        "INTERNAL_PAPER",
        None,
        NOW,
        "UNSUPPORTED_SIDE",
    )

    assert accepted.processed_at == UTC_NOW
    assert rejected.broker_order_ref is None
    with pytest.raises(FrozenInstanceError):
        accepted.broker_code = "OTHER"  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"broker_code": ""},
        {"broker_code": "X" * 33},
        {"broker_order_ref": "X" * 161},
        {"processed_at": datetime(2026, 7, 15)},
        {"rejection_code": "REJECTED"},
    ],
)
def test_invalid_accepted_result_is_rejected(changes: dict[str, object]) -> None:
    values = {
        "outcome": PaperBrokerSubmissionOutcome.ACCEPTED,
        "broker_code": "INTERNAL_PAPER",
        "broker_order_ref": "reference",
        "processed_at": UTC_NOW,
        "rejection_code": None,
    }
    values.update(changes)
    with pytest.raises(ValidationError):
        PaperOrderSubmissionResult(**values)  # type: ignore[arg-type]


def test_new_and_stored_orders_are_frozen_and_normalize_timestamps() -> None:
    new = order(submitted_at=NOW, accepted_at=NOW, updated_at=NOW)
    stored = StoredPaperOrder(
        **{field: getattr(new, field) for field in new.__dataclass_fields__},
        recorded_at=NOW,
    )

    assert new.submitted_at == UTC_NOW
    assert stored.recorded_at == UTC_NOW
    with pytest.raises(FrozenInstanceError):
        new.version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"version": 0},
        {"submitted_at": datetime(2026, 7, 15)},
        {"updated_at": UTC_NOW - timedelta(seconds=1)},
        {"accepted_at": UTC_NOW - timedelta(seconds=1)},
        {"status": PaperOrderStatus.ACCEPTED, "rejection_code": "REJECTED"},
        {
            "status": PaperOrderStatus.REJECTED,
            "accepted_at": None,
            "closed_at": UTC_NOW,
            "rejection_code": None,
        },
    ],
)
def test_invalid_order_contract_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        order(**changes)


def test_replace_does_not_mutate_source_contract() -> None:
    source = order()
    changed = replace(source, order_id=OrderID(UUID(int=4)))
    assert source.order_id != changed.order_id
