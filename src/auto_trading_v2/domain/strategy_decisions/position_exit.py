"""Pure deterministic policy for version-pinned position exit decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from auto_trading_v2.domain.primitives import Currency, Price, Rate
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from auto_trading_v2.domain.strategy_decisions.reason_codes import normalize_reason_codes


@dataclass(frozen=True, slots=True)
class PositionExitPolicy:
    """Stable threshold and freshness policy shared by supported entry strategies."""

    name: str
    version: str
    currency: Currency
    stop_loss_rate: Rate
    take_profit_rate: Rate
    maximum_holding_duration: timedelta
    snapshot_maximum_age: timedelta
    future_clock_skew_tolerance: timedelta

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or not self.name.replace("_", "").isalnum()
        ):
            raise StrategyValidationError("position exit policy name is invalid")
        if not isinstance(self.version, str) or not self.version or len(self.version) > 64:
            raise StrategyValidationError("position exit policy version is invalid")
        if not isinstance(self.currency, Currency):
            raise StrategyValidationError("position exit policy currency is invalid")
        if not isinstance(self.stop_loss_rate, Rate) or not isinstance(self.take_profit_rate, Rate):
            raise StrategyValidationError("position exit thresholds are invalid")
        if self.stop_loss_rate.value >= 0 or self.take_profit_rate.value <= 0:
            raise StrategyValidationError("position exit thresholds are invalid")
        if self.stop_loss_rate.value >= self.take_profit_rate.value:
            raise StrategyValidationError("position exit threshold ordering is invalid")
        for duration, label, allow_zero in (
            (self.maximum_holding_duration, "holding duration", False),
            (self.snapshot_maximum_age, "snapshot age", True),
            (self.future_clock_skew_tolerance, "clock skew", True),
        ):
            if not isinstance(duration, timedelta) or duration < timedelta(0):
                raise StrategyValidationError(f"position exit {label} is invalid")
            if not allow_zero and duration == timedelta(0):
                raise StrategyValidationError(f"position exit {label} is invalid")


@dataclass(frozen=True, slots=True)
class PositionExitEvaluation:
    """Pure exit action with ordered reasons and unquantized diagnostics."""

    action: StrategyAction
    reason_codes: tuple[str, ...]
    return_rate: Rate
    holding_duration: timedelta

    def __post_init__(self) -> None:
        if self.action not in {StrategyAction.EXIT_LONG, StrategyAction.SKIP}:
            raise StrategyValidationError("position exit action is invalid")
        if not isinstance(self.return_rate, Rate):
            raise StrategyValidationError("position exit return rate is invalid")
        if not isinstance(self.holding_duration, timedelta) or self.holding_duration < timedelta(0):
            raise StrategyValidationError("position exit holding duration is invalid")
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))


def evaluate_position_exit(
    *,
    average_cost_price: Price,
    current_price: Price,
    opened_at: datetime,
    snapshot_observed_at: datetime,
    policy: PositionExitPolicy,
) -> PositionExitEvaluation:
    """Evaluate inclusive stop-loss, take-profit, and elapsed-time thresholds."""

    if not isinstance(average_cost_price, Price) or not isinstance(current_price, Price):
        raise StrategyValidationError("position exit prices are invalid")
    if not isinstance(policy, PositionExitPolicy):
        raise StrategyValidationError("position exit policy is invalid")
    opened = normalize_utc(opened_at)
    observed = normalize_utc(snapshot_observed_at)
    holding_duration = observed - opened
    if holding_duration < timedelta(0):
        raise StrategyValidationError("position exit holding duration is invalid")

    return_rate = Rate((current_price.value - average_cost_price.value) / average_cost_price.value)
    reasons: list[str] = []
    if return_rate.value <= policy.stop_loss_rate.value:
        reasons.append("STOP_LOSS_TRIGGERED")
    if return_rate.value >= policy.take_profit_rate.value:
        reasons.append("TAKE_PROFIT_TRIGGERED")
    if holding_duration >= policy.maximum_holding_duration:
        reasons.append("TIME_EXIT_TRIGGERED")

    if reasons:
        reasons.append("EXIT_LONG_ALLOWED")
        action = StrategyAction.EXIT_LONG
    else:
        reasons.extend(("EXIT_CONDITIONS_NOT_MET", "POSITION_HOLD"))
        action = StrategyAction.SKIP
    return PositionExitEvaluation(action, tuple(reasons), return_rate, holding_duration)
