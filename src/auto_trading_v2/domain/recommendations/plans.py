"""Actionable Recommendation disposition and plan value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import Currency, Price, Rate
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc
from auto_trading_v2.domain.recommendations.errors import (
    RecommendationValidationError,
)


class RecommendationDisposition(StrEnum):
    """Canonical recommendation and non-recommendation outcomes."""

    RECOMMEND = "RECOMMEND"
    CONDITIONAL = "CONDITIONAL"
    WATCH = "WATCH"
    NO_RECOMMENDATION = "NO_RECOMMENDATION"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    MARKET_RISK = "MARKET_RISK"

    @property
    def actionable(self) -> bool:
        return self in {self.RECOMMEND, self.CONDITIONAL}


@dataclass(frozen=True, slots=True)
class RecommendationPlan:
    """Caller-supplied long plan; P1 validates but never calculates it."""

    currency: Currency
    entry_price_low: Price
    entry_price_high: Price
    target_price: Price
    stop_price: Price
    expected_holding_trading_days: TradingDayHorizon
    upside_probability: Rate
    target_probability: Rate
    stop_probability: Rate
    expected_value_rate: Rate
    reward_risk_ratio: Rate
    confidence: Rate
    valid_until: datetime

    def __post_init__(self) -> None:
        _require_type(self.currency, Currency, "currency")
        for label in ("entry_price_low", "entry_price_high", "target_price", "stop_price"):
            _require_type(getattr(self, label), Price, label)
        _require_type(
            self.expected_holding_trading_days,
            TradingDayHorizon,
            "expected_holding_trading_days",
        )
        for label in (
            "upside_probability",
            "target_probability",
            "stop_probability",
            "expected_value_rate",
            "reward_risk_ratio",
            "confidence",
        ):
            _require_type(getattr(self, label), Rate, label)
        if self.currency != Currency("USD"):
            raise RecommendationValidationError("P1 Recommendation 통화는 USD여야 합니다.")
        if not (
            self.stop_price.value
            < self.entry_price_low.value
            <= self.entry_price_high.value
            < self.target_price.value
        ):
            raise RecommendationValidationError("추천 가격 순서가 올바르지 않습니다.")
        for label in ("upside_probability", "target_probability", "stop_probability"):
            value = getattr(self, label).value
            if not 0 <= value <= 1:
                raise RecommendationValidationError(f"{label}는 0~1이어야 합니다.")
        if self.target_probability.value + self.stop_probability.value > 1:
            raise RecommendationValidationError("목표와 손절 확률의 합은 1 이하여야 합니다.")
        if self.expected_value_rate.value <= 0:
            raise RecommendationValidationError("expected_value_rate는 0보다 커야 합니다.")
        if self.reward_risk_ratio.value <= 0:
            raise RecommendationValidationError("reward_risk_ratio는 0보다 커야 합니다.")
        if not 0 <= self.confidence.value <= 1:
            raise RecommendationValidationError("confidence는 0~1이어야 합니다.")
        object.__setattr__(self, "valid_until", _timestamp(self.valid_until, "valid_until"))

    def as_json(self) -> dict[str, object]:
        """Return the canonical content representation used by the digest."""

        return {
            "confidence": _decimal(self.confidence.value),
            "currency": self.currency.serialize(),
            "entry_price_high": _decimal(self.entry_price_high.value),
            "entry_price_low": _decimal(self.entry_price_low.value),
            "expected_holding_trading_days": self.expected_holding_trading_days.value,
            "expected_value_rate": _decimal(self.expected_value_rate.value),
            "reward_risk_ratio": _decimal(self.reward_risk_ratio.value),
            "stop_price": _decimal(self.stop_price.value),
            "stop_probability": _decimal(self.stop_probability.value),
            "target_price": _decimal(self.target_price.value),
            "target_probability": _decimal(self.target_probability.value),
            "upside_probability": _decimal(self.upside_probability.value),
            "valid_until": UtcTimestamp(self.valid_until).serialize(),
        }


def _require_type(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise RecommendationValidationError(f"{label} 타입이 올바르지 않습니다.")


def _timestamp(value: datetime, label: str) -> datetime:
    try:
        return normalize_utc(value)
    except ValidationError:
        raise RecommendationValidationError(
            f"{label}은 timezone-aware datetime이어야 합니다."
        ) from None


def _decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
