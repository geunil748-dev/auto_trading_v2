from decimal import Decimal

import pytest

from auto_trading_v2.domain.filtering.checks import (
    breakout_check,
    entry_change_check,
    opening_change_check,
    price_range_check,
    volume_present_check,
)
from auto_trading_v2.domain.filtering.models import FilterOutcome, FilterSetName

from .helpers import definition, filter_input


@pytest.mark.parametrize("value", ["10", "300"])
def test_price_range_includes_boundaries(value: str) -> None:
    result = price_range_check(filter_input(last_price=value), definition(FilterSetName.STRICT))

    assert result.outcome is FilterOutcome.PASS
    assert result.reason_code == "PRICE_WITHIN_RANGE"


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("9.999999999999999999", "PRICE_BELOW_MINIMUM"),
        ("300.000000000000000001", "PRICE_ABOVE_MAXIMUM"),
    ],
)
def test_price_range_rejects_values_outside_boundaries(value: str, reason: str) -> None:
    result = price_range_check(filter_input(last_price=value), definition(FilterSetName.STRICT))

    assert result.outcome is FilterOutcome.FAIL
    assert result.reason_code == reason
    assert result.observed["last_price"] == value


@pytest.mark.parametrize(
    ("open_price", "outcome"),
    [("103", FilterOutcome.PASS), ("104", FilterOutcome.PASS), ("102.999", FilterOutcome.FAIL)],
)
def test_opening_change_three_percent_boundary(open_price: str, outcome: FilterOutcome) -> None:
    result = opening_change_check(
        filter_input(open_price=open_price, previous_close="100"),
        definition(FilterSetName.STRICT),
    )

    assert result.outcome is outcome


def test_opening_change_negative_fails_and_missing_close_is_not_evaluable() -> None:
    negative = opening_change_check(
        filter_input(open_price="90", previous_close="100"), definition(FilterSetName.STRICT)
    )
    missing = opening_change_check(
        filter_input(previous_close=None), definition(FilterSetName.STRICT)
    )

    assert negative.outcome is FilterOutcome.FAIL
    assert missing.outcome is FilterOutcome.NOT_EVALUABLE
    assert missing.reason_code == "PREVIOUS_CLOSE_MISSING"


@pytest.mark.parametrize(
    ("last_price", "outcome"),
    [
        ("115", FilterOutcome.PASS),
        ("114", FilterOutcome.PASS),
        ("115.0001", FilterOutcome.FAIL),
        ("90", FilterOutcome.PASS),
    ],
)
def test_entry_change_fifteen_percent_boundary(last_price: str, outcome: FilterOutcome) -> None:
    result = entry_change_check(
        filter_input(last_price=last_price, previous_close="100"),
        definition(FilterSetName.STRICT),
    )

    assert result.outcome is outcome


def test_entry_change_missing_close_is_not_evaluable() -> None:
    result = entry_change_check(filter_input(previous_close=None), definition(FilterSetName.STRICT))

    assert result.outcome is FilterOutcome.NOT_EVALUABLE
    assert result.reason_code == "PREVIOUS_CLOSE_MISSING"


@pytest.mark.parametrize(
    ("last_price", "outcome"),
    [
        ("25", FilterOutcome.PASS),
        ("25.000000000000000001", FilterOutcome.PASS),
        ("24.999999999999999999", FilterOutcome.FAIL),
    ],
)
def test_breakout_uses_exact_previous_range_target(last_price: str, outcome: FilterOutcome) -> None:
    result = breakout_check(filter_input(last_price=last_price), definition(FilterSetName.STRICT))

    assert result.outcome is outcome
    assert result.threshold == {"factor": "0.5", "target": "25.0"}


@pytest.mark.parametrize(
    ("volume", "outcome"),
    [(1, FilterOutcome.PASS), (0, FilterOutcome.FAIL), (None, FilterOutcome.FAIL)],
)
def test_volume_present_requires_positive_value(volume: int | None, outcome: FilterOutcome) -> None:
    result = volume_present_check(filter_input(volume=volume), definition(FilterSetName.STRICT))

    assert result.outcome is outcome


def test_change_details_preserve_fixed_point_decimal() -> None:
    result = opening_change_check(
        filter_input(open_price="0.103", previous_close="0.1"),
        definition(FilterSetName.STRICT),
    )

    observed = result.observed["opening_change"]
    assert observed == Decimal("0.03").to_eng_string()
    assert "E" not in str(observed)
