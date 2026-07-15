"""Pure semantic identity for deterministic paper fills."""

from auto_trading_v2.domain.paper_fills.errors import PaperFillValidationError
from auto_trading_v2.domain.primitives import OrderID


def paper_fill_execution_key(order_id: OrderID, sequence: int) -> str:
    """Return the exact v1 execution identity for one order sequence."""

    if not isinstance(order_id, OrderID):
        raise PaperFillValidationError("order identifier is invalid")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        raise PaperFillValidationError("fill sequence must be positive")
    key = (
        f"order:{order_id.serialize()}|fill-policy:internal-paper-split-fill|"
        f"version:v1|sequence:{sequence}"
    )
    if len(key) > 160:
        raise PaperFillValidationError("execution key is too long")
    return key
