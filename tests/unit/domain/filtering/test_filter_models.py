from dataclasses import FrozenInstanceError, replace

import pytest

from auto_trading_v2.domain.filtering.errors import FilterValidationError
from auto_trading_v2.domain.filtering.models import FilterInput, FilterSetName

from .helpers import definition, filter_input


def test_filter_input_is_immutable() -> None:
    value = filter_input()

    with pytest.raises(FrozenInstanceError):
        value.volume = 1  # type: ignore[misc]


@pytest.mark.parametrize("volume", [-1, True, "1"])
def test_filter_input_rejects_invalid_volume(volume: object) -> None:
    with pytest.raises(FilterValidationError):
        replace(filter_input(), volume=volume)  # type: ignore[arg-type]


def test_filter_input_rejects_non_price_values() -> None:
    with pytest.raises(FilterValidationError):
        FilterInput(
            symbol=filter_input().symbol,
            open_price="22.66",  # type: ignore[arg-type]
            last_price=filter_input().last_price,
            previous_high_price=filter_input().previous_high_price,
            previous_low_price=filter_input().previous_low_price,
            previous_close_price=filter_input().previous_close_price,
            volume=100,
        )


def test_filter_set_rejects_invalid_weight_and_hard_check_collections() -> None:
    original = definition(FilterSetName.STRICT)

    with pytest.raises(FilterValidationError):
        replace(original, weights=(object(),))  # type: ignore[arg-type]
    with pytest.raises(FilterValidationError):
        replace(original, hard_checks=(object(),))  # type: ignore[arg-type]
