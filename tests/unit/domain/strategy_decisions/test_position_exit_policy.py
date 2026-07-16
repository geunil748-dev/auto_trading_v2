from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.domain.primitives import Price, Rate
from auto_trading_v2.domain.strategy_decisions import (
    FIXED_POSITION_EXIT,
    PositionExitPolicy,
    StrategyAction,
    evaluate_position_exit,
)
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError

OPENED_AT = datetime(2026, 7, 16, 0, tzinfo=UTC)


def evaluate(price: str, holding: timedelta = timedelta(hours=1)):
    return evaluate_position_exit(
        average_cost_price=Price(Decimal("100")),
        current_price=Price(Decimal(price)),
        opened_at=OPENED_AT,
        snapshot_observed_at=OPENED_AT + holding,
        policy=FIXED_POSITION_EXIT,
    )


@pytest.mark.parametrize("price", ["95", "94.99"])
def test_stop_loss_is_inclusive(price: str) -> None:
    result = evaluate(price)

    assert result.action is StrategyAction.EXIT_LONG
    assert result.reason_codes == ("STOP_LOSS_TRIGGERED", "EXIT_LONG_ALLOWED")


def test_price_above_stop_boundary_does_not_trigger() -> None:
    result = evaluate("95.000000000000000001")

    assert result.action is StrategyAction.SKIP
    assert "STOP_LOSS_TRIGGERED" not in result.reason_codes


def test_take_profit_is_inclusive() -> None:
    result = evaluate("110")

    assert result.action is StrategyAction.EXIT_LONG
    assert result.reason_codes == ("TAKE_PROFIT_TRIGGERED", "EXIT_LONG_ALLOWED")


def test_price_below_take_profit_boundary_does_not_trigger() -> None:
    result = evaluate("109.999999999999999999")

    assert result.action is StrategyAction.SKIP
    assert "TAKE_PROFIT_TRIGGERED" not in result.reason_codes


def test_time_exit_is_inclusive_at_six_hours() -> None:
    result = evaluate("100", timedelta(hours=6))

    assert result.action is StrategyAction.EXIT_LONG
    assert result.reason_codes == ("TIME_EXIT_TRIGGERED", "EXIT_LONG_ALLOWED")


def test_time_exit_does_not_trigger_before_six_hours() -> None:
    result = evaluate("100", timedelta(hours=6) - timedelta(microseconds=1))

    assert result.action is StrategyAction.SKIP
    assert "TIME_EXIT_TRIGGERED" not in result.reason_codes


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (
            "110",
            ("TAKE_PROFIT_TRIGGERED", "TIME_EXIT_TRIGGERED", "EXIT_LONG_ALLOWED"),
        ),
        (
            "95",
            ("STOP_LOSS_TRIGGERED", "TIME_EXIT_TRIGGERED", "EXIT_LONG_ALLOWED"),
        ),
    ],
)
def test_price_and_time_reasons_keep_canonical_order(
    price: str,
    expected: tuple[str, ...],
) -> None:
    assert evaluate(price, timedelta(hours=6)).reason_codes == expected


def test_no_condition_returns_skip_and_hold_reasons() -> None:
    result = evaluate("100")

    assert result.action is StrategyAction.SKIP
    assert result.reason_codes == ("EXIT_CONDITIONS_NOT_MET", "POSITION_HOLD")
    assert result.return_rate == Rate(Decimal("0"))


def test_float_price_is_rejected() -> None:
    with pytest.raises(StrategyValidationError):
        evaluate_position_exit(
            average_cost_price=100.0,  # type: ignore[arg-type]
            current_price=Price(Decimal("100")),
            opened_at=OPENED_AT,
            snapshot_observed_at=OPENED_AT,
            policy=FIXED_POSITION_EXIT,
        )


@pytest.mark.parametrize(
    ("stop_loss", "take_profit"),
    [
        (Rate(Decimal("0.01")), FIXED_POSITION_EXIT.take_profit_rate),
        (FIXED_POSITION_EXIT.stop_loss_rate, Rate(Decimal("-0.01"))),
    ],
)
def test_invalid_thresholds_are_rejected(
    stop_loss: Rate,
    take_profit: Rate,
) -> None:
    with pytest.raises(StrategyValidationError):
        PositionExitPolicy(
            name=FIXED_POSITION_EXIT.name,
            version=FIXED_POSITION_EXIT.version,
            currency=FIXED_POSITION_EXIT.currency,
            stop_loss_rate=stop_loss,
            take_profit_rate=take_profit,
            maximum_holding_duration=FIXED_POSITION_EXIT.maximum_holding_duration,
            snapshot_maximum_age=FIXED_POSITION_EXIT.snapshot_maximum_age,
            future_clock_skew_tolerance=FIXED_POSITION_EXIT.future_clock_skew_tolerance,
        )


def test_negative_holding_duration_is_rejected() -> None:
    with pytest.raises(StrategyValidationError):
        evaluate("100", timedelta(microseconds=-1))


def test_fixed_policy_catalog_values_are_pinned() -> None:
    assert FIXED_POSITION_EXIT.name == "FIXED_POSITION_EXIT"
    assert FIXED_POSITION_EXIT.version == "v1"
    assert FIXED_POSITION_EXIT.currency.code == "USD"
    assert FIXED_POSITION_EXIT.stop_loss_rate == Rate(Decimal("-0.05"))
    assert FIXED_POSITION_EXIT.take_profit_rate == Rate(Decimal("0.10"))
    assert FIXED_POSITION_EXIT.maximum_holding_duration == timedelta(hours=6)
    assert FIXED_POSITION_EXIT.snapshot_maximum_age == timedelta(minutes=5)
    assert FIXED_POSITION_EXIT.future_clock_skew_tolerance == timedelta(seconds=30)
