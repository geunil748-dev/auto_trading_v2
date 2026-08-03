from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.domain.paper_fills import (
    INTERNAL_PAPER_SPLIT_FILL_POLICY,
    PaperFillHistoryValidationError,
    paper_fill_execution_key,
    validate_fill_history,
)
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import Currency, Money, OrderID, Price, Quantity

NOW = datetime(2026, 7, 16, 1, tzinfo=UTC)
ORDER_ID = OrderID(UUID(int=1))
USD = Currency("USD")
PRICE = Price(Decimal("25"))
PLAN = INTERNAL_PAPER_SPLIT_FILL_POLICY.plan(Quantity(40))


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: OrderID = ORDER_ID
    execution_key: str = paper_fill_execution_key(ORDER_ID, 1)
    fill_sequence: int = 1
    quantity: Quantity = Quantity(20)
    price: Price = PRICE
    fee: Money = Money(Decimal("0"), USD)
    executed_at: datetime = NOW


def validate(status: PaperOrderStatus, fills: tuple[Fill, ...]) -> Quantity:
    return validate_fill_history(
        order_id=ORDER_ID,
        order_status=status,
        order_accepted_at=NOW,
        plan=PLAN,
        reference_price=PRICE,
        fee_currency=USD,
        fills=fills,
    )


def test_empty_accepted_and_exact_first_partial_history_are_valid() -> None:
    assert validate(PaperOrderStatus.ACCEPTED, ()).value == 0
    first = Fill()
    history = (first,)

    assert validate(PaperOrderStatus.PARTIALLY_FILLED, history).value == 20
    assert history == (first,)


@pytest.mark.parametrize(
    "changed",
    [
        {"fill_sequence": 2},
        {"quantity": Quantity(19)},
        {"execution_key": "wrong"},
        {"order_id": OrderID(UUID(int=2))},
        {"price": Price(Decimal("26"))},
        {"fee": Money(Decimal("1"), USD)},
        {"fee": Money(Decimal("0"), Currency("KRW"))},
        {"executed_at": NOW - timedelta(seconds=1)},
    ],
)
def test_invalid_first_fill_fact_is_rejected(changed: dict[str, object]) -> None:
    with pytest.raises(PaperFillHistoryValidationError):
        validate(PaperOrderStatus.PARTIALLY_FILLED, (replace(Fill(), **changed),))


def test_gap_too_many_and_state_history_mismatch_are_rejected() -> None:
    second = replace(
        Fill(),
        fill_sequence=2,
        execution_key=paper_fill_execution_key(ORDER_ID, 2),
    )
    with pytest.raises(PaperFillHistoryValidationError):
        validate(PaperOrderStatus.PARTIALLY_FILLED, (Fill(), second, second))
    with pytest.raises(PaperFillHistoryValidationError):
        validate(PaperOrderStatus.ACCEPTED, (Fill(),))
    with pytest.raises(PaperFillHistoryValidationError):
        validate(PaperOrderStatus.PARTIALLY_FILLED, ())
