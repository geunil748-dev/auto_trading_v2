from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from auto_trading_v2.domain.filtering.catalog import BUILT_IN_FILTER_SETS
from auto_trading_v2.domain.filtering.engine import DeterministicFilterEngine
from auto_trading_v2.domain.filtering.models import (
    FilterCheckName,
    FilterCheckWeight,
    FilterEvaluationResult,
    FilterInput,
    FilterSetDefinition,
    FilterSetName,
)
from auto_trading_v2.domain.primitives import Price, Symbol


def price(value: str) -> Price:
    return Price(Decimal(value))


def filter_input(
    *,
    open_price: str = "22.66",
    last_price: str = "25",
    previous_high: str = "20",
    previous_low: str = "10",
    previous_close: str | None = "22",
    volume: int | None = 100,
) -> FilterInput:
    return FilterInput(
        symbol=Symbol("AAPL"),
        open_price=price(open_price),
        last_price=price(last_price),
        previous_high_price=price(previous_high),
        previous_low_price=price(previous_low),
        previous_close_price=None if previous_close is None else price(previous_close),
        volume=volume,
    )


def definition(name: FilterSetName) -> FilterSetDefinition:
    return next(item for item in BUILT_IN_FILTER_SETS if item.name is name)


def evaluate_all(value: FilterInput) -> dict[FilterSetName, FilterEvaluationResult]:
    engine = DeterministicFilterEngine()
    return {item.name: engine.evaluate(value, item) for item in BUILT_IN_FILTER_SETS}


def with_weights(
    original: FilterSetDefinition,
    weights: tuple[str, str, str, str, str],
) -> FilterSetDefinition:
    return replace(
        original,
        weights=tuple(
            FilterCheckWeight(name, Decimal(weight))
            for name, weight in zip(FilterCheckName, weights, strict=True)
        ),
    )
