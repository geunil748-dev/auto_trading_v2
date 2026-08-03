"""Pure validation of canonical fill history before the next execution."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from auto_trading_v2.domain.paper_fills.errors import PaperFillHistoryValidationError
from auto_trading_v2.domain.paper_fills.execution_keys import paper_fill_execution_key
from auto_trading_v2.domain.paper_fills.models import FillQuantityPlan
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import Currency, Money, OrderID, Price, Quantity
from auto_trading_v2.domain.primitives.time import normalize_utc


class FillHistoryEntry(Protocol):
    @property
    def order_id(self) -> OrderID: ...

    @property
    def execution_key(self) -> str: ...

    @property
    def fill_sequence(self) -> int: ...

    @property
    def quantity(self) -> Quantity: ...

    @property
    def price(self) -> Price: ...

    @property
    def fee(self) -> Money: ...

    @property
    def executed_at(self) -> datetime: ...


def validate_fill_history(
    *,
    order_id: OrderID,
    order_status: PaperOrderStatus,
    order_accepted_at: datetime,
    plan: FillQuantityPlan,
    reference_price: Price,
    fee_currency: Currency,
    fills: Sequence[FillHistoryEntry],
) -> Quantity:
    """Validate every stored fact and return its cumulative quantity."""

    accepted_at = normalize_utc(order_accepted_at)
    if len(fills) > len(plan.quantities):
        raise PaperFillHistoryValidationError("too_many_fills")
    cumulative = 0
    for expected_sequence, fill in enumerate(fills, start=1):
        if fill.order_id != order_id:
            raise PaperFillHistoryValidationError("order_mismatch")
        if fill.fill_sequence != expected_sequence:
            raise PaperFillHistoryValidationError("sequence_mismatch")
        if fill.execution_key != paper_fill_execution_key(order_id, expected_sequence):
            raise PaperFillHistoryValidationError("execution_key_mismatch")
        if fill.quantity != plan.quantities[expected_sequence - 1]:
            raise PaperFillHistoryValidationError("quantity_mismatch")
        if fill.price != reference_price:
            raise PaperFillHistoryValidationError("price_mismatch")
        if fill.fee.amount != Decimal("0"):
            raise PaperFillHistoryValidationError("nonzero_fee")
        if fill.fee.currency != fee_currency:
            raise PaperFillHistoryValidationError("fee_currency_mismatch")
        if normalize_utc(fill.executed_at) < accepted_at:
            raise PaperFillHistoryValidationError("execution_precedes_acceptance")
        cumulative += fill.quantity.value
        if cumulative > plan.requested_quantity.value:
            raise PaperFillHistoryValidationError("overfill")

    if order_status is PaperOrderStatus.ACCEPTED:
        if fills:
            raise PaperFillHistoryValidationError("accepted_order_has_fills")
    elif order_status is PaperOrderStatus.PARTIALLY_FILLED:
        if plan.requested_quantity.value < 2 or len(fills) != 1:
            raise PaperFillHistoryValidationError("partial_order_history_shape")
        if cumulative >= plan.requested_quantity.value:
            raise PaperFillHistoryValidationError("partial_order_not_remaining")
    else:
        raise PaperFillHistoryValidationError("order_status_not_fillable")
    return Quantity(cumulative)
