from uuid import UUID

import pytest

from auto_trading_v2.domain.paper_fills import (
    PaperFillValidationError,
    paper_fill_execution_key,
)
from auto_trading_v2.domain.primitives import OrderID


def test_execution_key_uses_exact_v1_semantic_identity() -> None:
    order_id = OrderID(UUID("40000000-0000-0000-0000-000000000001"))

    first = paper_fill_execution_key(order_id, 1)
    second = paper_fill_execution_key(order_id, 2)

    assert first == (
        f"order:{order_id}|fill-policy:internal-paper-split-fill|version:v1|sequence:1"
    )
    assert first == paper_fill_execution_key(order_id, 1)
    assert first != second
    assert first != paper_fill_execution_key(OrderID(UUID(int=2)), 1)
    assert len(first) <= 160
    assert not any(character.isspace() for character in first)


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_execution_key_rejects_invalid_sequence(sequence: int) -> None:
    with pytest.raises(PaperFillValidationError):
        paper_fill_execution_key(OrderID(UUID(int=1)), sequence)
