"""Five explicit Decimal-only checks over canonical market values."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from auto_trading_v2.domain.filtering.errors import FilterValidationError
from auto_trading_v2.domain.filtering.models import (
    FilterCheckName,
    FilterCheckResult,
    FilterInput,
    FilterOutcome,
    FilterSetDefinition,
)
from auto_trading_v2.domain.strategy.breakout import volatility_breakout_price


def decimal_text(value: Decimal) -> str:
    """Render a Decimal in fixed-point form without quantizing it."""

    return format(value, "f")


def _weight(definition: FilterSetDefinition, name: FilterCheckName) -> Decimal:
    for item in definition.weights:
        if item.name is name:
            return item.weight
    raise FilterValidationError("filter definition is missing a check weight")


def _result(
    definition: FilterSetDefinition,
    name: FilterCheckName,
    outcome: FilterOutcome,
    reason_code: str,
    observed: dict[str, str | int | bool | None],
    threshold: dict[str, str | int | bool | None],
) -> FilterCheckResult:
    return FilterCheckResult(
        name=name,
        outcome=outcome,
        reason_code=reason_code,
        hard=name in definition.hard_checks,
        weight=_weight(definition, name),
        observed=observed,
        threshold=threshold,
    )


def price_range_check(
    filter_input: FilterInput, definition: FilterSetDefinition
) -> FilterCheckResult:
    value = filter_input.last_price.value
    minimum = definition.thresholds.minimum_price.value
    maximum = definition.thresholds.maximum_price.value
    if value < minimum:
        outcome, reason = FilterOutcome.FAIL, "PRICE_BELOW_MINIMUM"
    elif value > maximum:
        outcome, reason = FilterOutcome.FAIL, "PRICE_ABOVE_MAXIMUM"
    else:
        outcome, reason = FilterOutcome.PASS, "PRICE_WITHIN_RANGE"
    return _result(
        definition,
        FilterCheckName.PRICE_RANGE,
        outcome,
        reason,
        {"last_price": decimal_text(value)},
        {"minimum": decimal_text(minimum), "maximum": decimal_text(maximum)},
    )


def _change(current: Decimal, previous: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 38
        context.rounding = ROUND_HALF_EVEN
        return (current - previous) / previous


def opening_change_check(
    filter_input: FilterInput, definition: FilterSetDefinition
) -> FilterCheckResult:
    minimum = definition.thresholds.minimum_opening_change
    previous_close = filter_input.previous_close_price
    if previous_close is None:
        return _result(
            definition,
            FilterCheckName.OPENING_CHANGE_MIN,
            FilterOutcome.NOT_EVALUABLE,
            "PREVIOUS_CLOSE_MISSING",
            {"opening_change": None},
            {"minimum": decimal_text(minimum)},
        )
    change = _change(filter_input.open_price.value, previous_close.value)
    outcome = FilterOutcome.PASS if change >= minimum else FilterOutcome.FAIL
    reason = (
        "OPENING_CHANGE_MET" if outcome is FilterOutcome.PASS else "OPENING_CHANGE_BELOW_MINIMUM"
    )
    return _result(
        definition,
        FilterCheckName.OPENING_CHANGE_MIN,
        outcome,
        reason,
        {"opening_change": decimal_text(change)},
        {"minimum": decimal_text(minimum)},
    )


def entry_change_check(
    filter_input: FilterInput, definition: FilterSetDefinition
) -> FilterCheckResult:
    maximum = definition.thresholds.maximum_entry_change
    previous_close = filter_input.previous_close_price
    if previous_close is None:
        return _result(
            definition,
            FilterCheckName.ENTRY_CHANGE_MAX,
            FilterOutcome.NOT_EVALUABLE,
            "PREVIOUS_CLOSE_MISSING",
            {"entry_change": None},
            {"maximum": decimal_text(maximum)},
        )
    change = _change(filter_input.last_price.value, previous_close.value)
    outcome = FilterOutcome.PASS if change <= maximum else FilterOutcome.FAIL
    reason = (
        "ENTRY_CHANGE_WITHIN_LIMIT"
        if outcome is FilterOutcome.PASS
        else "ENTRY_CHANGE_ABOVE_MAXIMUM"
    )
    return _result(
        definition,
        FilterCheckName.ENTRY_CHANGE_MAX,
        outcome,
        reason,
        {"entry_change": decimal_text(change)},
        {"maximum": decimal_text(maximum)},
    )


def breakout_check(filter_input: FilterInput, definition: FilterSetDefinition) -> FilterCheckResult:
    factor = definition.thresholds.breakout_factor
    with localcontext() as context:
        context.prec = 38
        context.rounding = ROUND_HALF_EVEN
        target = volatility_breakout_price(
            filter_input.previous_high_price,
            filter_input.previous_high_price,
            filter_input.previous_low_price,
            factor,
        ).value
    outcome = FilterOutcome.PASS if filter_input.last_price.value >= target else FilterOutcome.FAIL
    reason = "BREAKOUT_TRIGGERED" if outcome is FilterOutcome.PASS else "BREAKOUT_NOT_TRIGGERED"
    return _result(
        definition,
        FilterCheckName.BREAKOUT_TRIGGERED,
        outcome,
        reason,
        {"last_price": decimal_text(filter_input.last_price.value)},
        {"factor": decimal_text(factor), "target": decimal_text(target)},
    )


def volume_present_check(
    filter_input: FilterInput, definition: FilterSetDefinition
) -> FilterCheckResult:
    passed = filter_input.volume is not None and filter_input.volume > 0
    return _result(
        definition,
        FilterCheckName.VOLUME_PRESENT,
        FilterOutcome.PASS if passed else FilterOutcome.FAIL,
        "VOLUME_PRESENT" if passed else "VOLUME_MISSING_OR_ZERO",
        {"volume": filter_input.volume},
        {"positive_required": True},
    )


def evaluate_checks(
    filter_input: FilterInput, definition: FilterSetDefinition
) -> tuple[FilterCheckResult, ...]:
    """Evaluate the five checks in their fixed canonical order."""

    return (
        price_range_check(filter_input, definition),
        opening_change_check(filter_input, definition),
        entry_change_check(filter_input, definition),
        breakout_check(filter_input, definition),
        volume_present_check(filter_input, definition),
    )
