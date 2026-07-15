"""Paper-order states and submission outcomes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.paper_orders.errors import PaperOrderValidationError


class PaperOrderStatus(StrEnum):
    """Canonical states supported by the existing paper_orders table."""

    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PaperBrokerSubmissionOutcome(StrEnum):
    """The two valid outcomes of submitting an order to a paper broker."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


def validate_paper_order_state(
    *,
    status: PaperOrderStatus,
    accepted_at: datetime | None,
    closed_at: datetime | None,
    rejection_code: str | None,
) -> None:
    """Validate the timestamp and rejection-code shape for one state."""

    if not isinstance(status, PaperOrderStatus):
        raise PaperOrderValidationError("paper order status is invalid")
    if rejection_code is not None and (
        not isinstance(rejection_code, str)
        or not rejection_code
        or rejection_code != rejection_code.strip()
        or len(rejection_code) > 64
    ):
        raise PaperOrderValidationError("paper order rejection code is invalid")

    if status is PaperOrderStatus.CREATED:
        valid = accepted_at is None and closed_at is None and rejection_code is None
    elif status in {PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED}:
        valid = accepted_at is not None and closed_at is None and rejection_code is None
    elif status is PaperOrderStatus.FILLED:
        valid = accepted_at is not None and closed_at is not None and rejection_code is None
    elif status is PaperOrderStatus.REJECTED:
        valid = accepted_at is None and closed_at is not None and rejection_code is not None
    else:
        valid = closed_at is not None and rejection_code is None
    if not valid:
        raise PaperOrderValidationError("paper order state is inconsistent")
