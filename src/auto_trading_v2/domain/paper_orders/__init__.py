"""Canonical paper-order domain values."""

from auto_trading_v2.domain.paper_orders.errors import PaperOrderValidationError
from auto_trading_v2.domain.paper_orders.models import (
    PaperBrokerSubmissionOutcome,
    PaperOrderStatus,
    validate_paper_order_state,
)
from auto_trading_v2.domain.paper_orders.references import (
    INTERNAL_PAPER_BROKER_CODE,
    INTERNAL_PAPER_REFERENCE_POLICY_NAME,
    INTERNAL_PAPER_REFERENCE_POLICY_VERSION,
    internal_paper_broker_reference,
)

__all__ = [
    "INTERNAL_PAPER_BROKER_CODE",
    "INTERNAL_PAPER_REFERENCE_POLICY_NAME",
    "INTERNAL_PAPER_REFERENCE_POLICY_VERSION",
    "PaperBrokerSubmissionOutcome",
    "PaperOrderStatus",
    "PaperOrderValidationError",
    "internal_paper_broker_reference",
    "validate_paper_order_state",
]
