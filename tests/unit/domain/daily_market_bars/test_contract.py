from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.primitives import Currency
from tests.unit.domain.daily_market_bars.helpers import bar_input


@pytest.mark.parametrize(
    "basis",
    [DailyMarketBarAdjustmentBasis.RAW, DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED],
)
def test_raw_and_split_adjusted_completed_bars_are_valid(
    basis: DailyMarketBarAdjustmentBasis,
) -> None:
    source = replace(bar_input(), adjustment_basis=basis)

    assert source.adjustment_basis is basis
    assert source.currency == Currency("USD")


@pytest.mark.parametrize(
    "changes",
    [
        {"currency": Currency("KRW")},
        {"open_price": 100.0},
        {"open_price": Decimal("NaN")},
        {"high_price": Decimal("Infinity")},
        {"low_price": Decimal(0)},
        {"volume": -1},
        {"volume": True},
        {"observed_at": datetime(2026, 1, 1, 1)},
        {"available_at": datetime(2026, 1, 1, 1)},
        {"source_code": ""},
        {"source_code": "bad/source"},
        {"source_record_key": "https://provider.example/secret"},
        {"source_version": ""},
    ],
)
def test_invalid_scalar_contracts_are_rejected(changes: dict[str, object]) -> None:
    source = bar_input()
    values = {name: getattr(source, name) for name in DailyMarketBarInput.__dataclass_fields__}
    values.update(changes)

    with pytest.raises(DailyMarketBarValidationError):
        DailyMarketBarInput(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"high_price": Decimal(97)},
        {"low_price": Decimal(101)},
        {"high_price": Decimal(99), "low_price": Decimal(98)},
    ],
)
def test_inconsistent_ohlc_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(DailyMarketBarValidationError):
        replace(bar_input(), **changes)


def test_observed_after_available_is_rejected() -> None:
    source = bar_input()

    with pytest.raises(DailyMarketBarValidationError):
        replace(source, observed_at=source.available_at.replace(hour=23, minute=1))


def test_volume_none_and_zero_are_valid() -> None:
    assert replace(bar_input(), volume=None).volume is None
    assert replace(bar_input(), volume=0).volume == 0
