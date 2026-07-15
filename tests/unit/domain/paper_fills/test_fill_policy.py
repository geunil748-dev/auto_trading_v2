from dataclasses import FrozenInstanceError

import pytest

from auto_trading_v2.domain.paper_fills import (
    INTERNAL_PAPER_SPLIT_FILL_POLICY,
    INTERNAL_PAPER_SPLIT_FILL_POLICY_NAME,
    INTERNAL_PAPER_SPLIT_FILL_POLICY_VERSION,
    PaperFillValidationError,
)
from auto_trading_v2.domain.primitives import Quantity


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(1, (1,)), (2, (1, 1)), (3, (1, 2)), (40, (20, 20)), (41, (20, 21))],
)
def test_exact_deterministic_split_plan(requested: int, expected: tuple[int, ...]) -> None:
    first = INTERNAL_PAPER_SPLIT_FILL_POLICY.plan(Quantity(requested))
    second = INTERNAL_PAPER_SPLIT_FILL_POLICY.plan(Quantity(requested))

    assert first == second
    assert first.policy_name == INTERNAL_PAPER_SPLIT_FILL_POLICY_NAME
    assert first.policy_version == INTERNAL_PAPER_SPLIT_FILL_POLICY_VERSION
    assert tuple(item.value for item in first.quantities) == expected
    assert all(item.value > 0 for item in first.quantities)
    assert sum(item.value for item in first.quantities) == requested
    assert len(first.quantities) <= 2
    with pytest.raises(FrozenInstanceError):
        first.quantities = ()  # type: ignore[misc]


def test_policy_rejects_zero_and_bool_without_random_state() -> None:
    with pytest.raises(PaperFillValidationError):
        INTERNAL_PAPER_SPLIT_FILL_POLICY.plan(Quantity(0))
    with pytest.raises(PaperFillValidationError):
        INTERNAL_PAPER_SPLIT_FILL_POLICY.plan(True)  # type: ignore[arg-type]
