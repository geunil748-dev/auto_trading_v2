"""Pure PaperOrder transition rules caused only by canonical fills."""

from datetime import datetime

from auto_trading_v2.domain.paper_fills.errors import PaperFillValidationError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus

_ALLOWED_TRANSITIONS = frozenset(
    {
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.FILLED),
        (PaperOrderStatus.PARTIALLY_FILLED, PaperOrderStatus.FILLED),
    }
)


def validate_fill_transition(
    *,
    expected_status: PaperOrderStatus,
    new_status: PaperOrderStatus,
    closed_at: datetime | None,
    updated_at: datetime,
) -> None:
    """Accept only forward fill transitions and their terminal timestamp shape."""

    if (expected_status, new_status) not in _ALLOWED_TRANSITIONS:
        raise PaperFillValidationError("paper order fill transition is invalid")
    if new_status is PaperOrderStatus.PARTIALLY_FILLED:
        if closed_at is not None:
            raise PaperFillValidationError("partial fill transition must stay open")
    elif closed_at is None or closed_at != updated_at:
        raise PaperFillValidationError("filled transition requires matching closed_at")
