"""Pure deterministic reference policy for the internal paper broker."""

from auto_trading_v2.domain.paper_orders.errors import PaperOrderValidationError
from auto_trading_v2.domain.primitives import ClientOrderID

INTERNAL_PAPER_BROKER_CODE = "INTERNAL_PAPER"
INTERNAL_PAPER_REFERENCE_POLICY_NAME = "INTERNAL_PAPER_REFERENCE"
INTERNAL_PAPER_REFERENCE_POLICY_VERSION = "v1"


def internal_paper_broker_reference(client_order_id: ClientOrderID) -> str:
    """Return the stable v1 broker reference for a client order."""

    if not isinstance(client_order_id, ClientOrderID):
        raise PaperOrderValidationError("client order identifier is invalid")
    return f"internal-paper:v1:{client_order_id.serialize()}"
