from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.paper_fills import PaperOrderFillTransition
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import OrderID

NOW = datetime(2026, 7, 16, 10, tzinfo=timezone(timedelta(hours=9)))
UTC_NOW = datetime(2026, 7, 16, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("old", "new", "closed"),
    [
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED, None),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.FILLED, NOW),
        (PaperOrderStatus.PARTIALLY_FILLED, PaperOrderStatus.FILLED, NOW),
    ],
)
def test_exact_fill_transitions_are_valid_and_normalized(
    old: PaperOrderStatus, new: PaperOrderStatus, closed: datetime | None
) -> None:
    value = PaperOrderFillTransition(OrderID(UUID(int=1)), old, 1, new, closed, NOW)
    assert value.updated_at == UTC_NOW
    assert value.closed_at is None or value.closed_at == UTC_NOW


@pytest.mark.parametrize(
    ("old", "new", "closed", "version"),
    [
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.ACCEPTED, None, 1),
        (PaperOrderStatus.PARTIALLY_FILLED, PaperOrderStatus.PARTIALLY_FILLED, None, 1),
        (PaperOrderStatus.FILLED, PaperOrderStatus.PARTIALLY_FILLED, None, 1),
        (PaperOrderStatus.REJECTED, PaperOrderStatus.FILLED, NOW, 1),
        (PaperOrderStatus.CREATED, PaperOrderStatus.FILLED, NOW, 1),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED, NOW, 1),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.FILLED, None, 1),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.FILLED, NOW, 0),
    ],
)
def test_invalid_fill_transitions_are_rejected(
    old: PaperOrderStatus,
    new: PaperOrderStatus,
    closed: datetime | None,
    version: int,
) -> None:
    with pytest.raises(ValidationError):
        PaperOrderFillTransition(OrderID(UUID(int=1)), old, version, new, closed, NOW)
