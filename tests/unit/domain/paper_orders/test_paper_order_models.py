from datetime import UTC, datetime, timedelta

import pytest

from auto_trading_v2.domain.paper_orders import (
    PaperBrokerSubmissionOutcome,
    PaperOrderStatus,
    PaperOrderValidationError,
    validate_paper_order_state,
)

NOW = datetime(2026, 7, 15, 1, tzinfo=UTC)


def test_status_and_outcome_values_are_exact() -> None:
    assert tuple(PaperOrderStatus) == (
        PaperOrderStatus.CREATED,
        PaperOrderStatus.ACCEPTED,
        PaperOrderStatus.PARTIALLY_FILLED,
        PaperOrderStatus.FILLED,
        PaperOrderStatus.CANCELLED,
        PaperOrderStatus.REJECTED,
        PaperOrderStatus.EXPIRED,
    )
    assert tuple(PaperBrokerSubmissionOutcome) == (
        PaperBrokerSubmissionOutcome.ACCEPTED,
        PaperBrokerSubmissionOutcome.REJECTED,
    )
    with pytest.raises(ValueError):
        PaperOrderStatus("UNKNOWN")
    with pytest.raises(ValueError):
        PaperBrokerSubmissionOutcome("FILLED")


@pytest.mark.parametrize(
    ("status", "accepted_at", "closed_at", "rejection_code"),
    [
        (PaperOrderStatus.CREATED, None, None, None),
        (PaperOrderStatus.ACCEPTED, NOW, None, None),
        (PaperOrderStatus.PARTIALLY_FILLED, NOW, None, None),
        (PaperOrderStatus.FILLED, NOW, NOW + timedelta(seconds=1), None),
        (PaperOrderStatus.REJECTED, None, NOW, "UNSUPPORTED_SIDE"),
        (PaperOrderStatus.CANCELLED, None, NOW, None),
        (PaperOrderStatus.CANCELLED, NOW, NOW, None),
        (PaperOrderStatus.EXPIRED, None, NOW, None),
        (PaperOrderStatus.EXPIRED, NOW, NOW, None),
    ],
)
def test_every_canonical_state_accepts_its_valid_shape(
    status: PaperOrderStatus,
    accepted_at: datetime | None,
    closed_at: datetime | None,
    rejection_code: str | None,
) -> None:
    validate_paper_order_state(
        status=status,
        accepted_at=accepted_at,
        closed_at=closed_at,
        rejection_code=rejection_code,
    )


@pytest.mark.parametrize(
    ("status", "accepted_at", "closed_at", "rejection_code"),
    [
        (PaperOrderStatus.CREATED, NOW, None, None),
        (PaperOrderStatus.ACCEPTED, None, None, None),
        (PaperOrderStatus.PARTIALLY_FILLED, NOW, NOW, None),
        (PaperOrderStatus.FILLED, NOW, None, None),
        (PaperOrderStatus.REJECTED, NOW, NOW, "REJECTED"),
        (PaperOrderStatus.REJECTED, None, NOW, None),
        (PaperOrderStatus.CANCELLED, None, None, None),
        (PaperOrderStatus.EXPIRED, None, NOW, "REJECTED"),
    ],
)
def test_inconsistent_state_shapes_are_rejected(
    status: PaperOrderStatus,
    accepted_at: datetime | None,
    closed_at: datetime | None,
    rejection_code: str | None,
) -> None:
    with pytest.raises(PaperOrderValidationError):
        validate_paper_order_state(
            status=status,
            accepted_at=accepted_at,
            closed_at=closed_at,
            rejection_code=rejection_code,
        )
