"""Payload-safe application errors for deterministic PaperFill execution."""

from __future__ import annotations

import re

from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import OrderID

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _safe_label(value: str, fallback: str) -> str:
    return value if isinstance(value, str) and _SAFE_LABEL.fullmatch(value) else fallback


class PaperOrderNotFoundError(RuntimeError):
    """The requested canonical PaperOrder does not exist."""

    def __init__(self, order_id: OrderID) -> None:
        self.order_id = order_id
        super().__init__(f"paper order not found: {order_id.serialize()}")


class PaperOrderNotFillableError(RuntimeError):
    """The current PaperOrder state cannot accept another fill."""

    def __init__(self, order_id: OrderID, status: PaperOrderStatus) -> None:
        self.order_id = order_id
        self.status = status
        super().__init__(f"paper order is not fillable: {order_id.serialize()}/{status.value}")


class UnsupportedPaperOrderBrokerError(RuntimeError):
    """The order was not accepted by the deterministic internal broker."""

    def __init__(self, broker_code: str) -> None:
        self.broker_code = _safe_label(broker_code, "unknown_broker")
        super().__init__(f"unsupported paper order broker: {self.broker_code}")


class PaperFillSourceError(RuntimeError):
    """The canonical source chain cannot safely produce a fill."""

    def __init__(self, order_id: OrderID, reason: str) -> None:
        self.order_id = order_id
        self.reason = _safe_label(reason, "invalid_source")
        super().__init__(f"paper fill source invalid: {order_id.serialize()}/{self.reason}")


class InvalidPaperFillHistoryError(RuntimeError):
    """Existing canonical fills are inconsistent with policy or order state."""

    def __init__(self, order_id: OrderID, reason: str) -> None:
        self.order_id = order_id
        self.reason = _safe_label(reason, "invalid_history")
        super().__init__(f"paper fill history invalid: {order_id.serialize()}/{self.reason}")


class PaperFillConflictError(RuntimeError):
    """A canonical fill identity is already occupied."""

    def __init__(self, order_id: OrderID, fill_sequence: int, category: str) -> None:
        self.order_id = order_id
        self.fill_sequence = fill_sequence
        self.category = _safe_label(category, "conflict")
        super().__init__(
            f"paper fill conflict: {order_id.serialize()}/{fill_sequence}/{self.category}"
        )


class PaperOrderConcurrencyError(RuntimeError):
    """The order changed after its next fill was planned."""

    def __init__(self, order_id: OrderID, category: str = "stale_order") -> None:
        self.order_id = order_id
        self.category = _safe_label(category, "concurrency_conflict")
        super().__init__(
            f"paper order concurrency conflict: {order_id.serialize()}/{self.category}"
        )
