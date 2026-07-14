from copy import deepcopy

import pytest

from auto_trading_v2.domain.strategy_decisions.catalog import STRICT_ENTRY
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError
from auto_trading_v2.domain.strategy_decisions.reason_codes import (
    extract_blocking_reason_codes,
    normalize_reason_codes,
    validate_reason_code,
)

from .helpers import signal


@pytest.mark.parametrize("value", ["A", "HARD_CHECK_FAILED", "A1_B2", "A" * 64])
def test_valid_reason_codes(value: str) -> None:
    assert validate_reason_code(value) == value


@pytest.mark.parametrize("value", ["", "lowercase", "HAS SPACE", "_START", "A" * 65])
def test_invalid_reason_codes_are_rejected_without_echo(value: str) -> None:
    with pytest.raises(StrategyValidationError) as captured:
        validate_reason_code(value)

    if value:
        assert value not in str(captured.value)


def test_filter_blocking_codes_deduplicate_in_original_order() -> None:
    details = {
        "blocking_reason_codes": [
            "HARD_CHECK_FAILED",
            "SCORE_BELOW_MINIMUM",
            "HARD_CHECK_FAILED",
        ]
    }

    assert extract_blocking_reason_codes(details, require_non_empty=True) == (
        "HARD_CHECK_FAILED",
        "SCORE_BELOW_MINIMUM",
    )


@pytest.mark.parametrize(
    "details",
    [
        {},
        {"blocking_reason_codes": "HARD_CHECK_FAILED"},
        {"blocking_reason_codes": [1]},
        {"blocking_reason_codes": ["lowercase"]},
        {"blocking_reason_codes": [f"CODE_{index}" for index in range(17)]},
    ],
)
def test_invalid_details_shape_is_rejected_without_payload(details: dict[str, object]) -> None:
    sentinel = "SHOULD_NEVER_APPEAR_PR6_a71c2f"
    details["secret"] = sentinel

    with pytest.raises(StrategyValidationError) as captured:
        signal(STRICT_ENTRY, details=details)  # type: ignore[arg-type]

    assert sentinel not in str(captured.value)
    assert sentinel not in repr(captured.value)


def test_failed_evaluation_requires_blocking_reason() -> None:
    with pytest.raises(StrategyValidationError):
        signal(STRICT_ENTRY, passed=False, blocking=[])


def test_details_are_deeply_immutable_and_input_is_unchanged() -> None:
    details = {"blocking_reason_codes": [], "nested": {"values": ["A"]}}
    before = deepcopy(details)
    value = signal(STRICT_ENTRY, details=details)

    details["nested"]["values"].append("B")  # type: ignore[index,union-attr]

    assert before == {"blocking_reason_codes": [], "nested": {"values": ["A"]}}
    assert value.details["nested"] != details["nested"]


def test_persisted_reason_codes_reject_duplicates() -> None:
    with pytest.raises(StrategyValidationError):
        normalize_reason_codes(("A", "A"))
