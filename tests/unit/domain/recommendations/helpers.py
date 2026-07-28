from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import (
    Currency,
    FeatureSnapshotID,
    Price,
    Rate,
)
from auto_trading_v2.domain.recommendations import (
    RecommendationDisposition,
    RecommendationInput,
    RecommendationPlan,
)

GENERATED_AT = datetime(2026, 7, 28, 5, tzinfo=UTC)


def plan(**overrides: object) -> RecommendationPlan:
    values: dict[str, object] = {
        "currency": Currency("USD"),
        "entry_price_low": Price(Decimal("100.00")),
        "entry_price_high": Price(Decimal("101.00")),
        "target_price": Price(Decimal("120.00")),
        "stop_price": Price(Decimal("95.00")),
        "expected_holding_trading_days": TradingDayHorizon(3),
        "upside_probability": Rate(Decimal("0.65")),
        "target_probability": Rate(Decimal("0.55")),
        "stop_probability": Rate(Decimal("0.20")),
        "expected_value_rate": Rate(Decimal("0.12")),
        "reward_risk_ratio": Rate(Decimal("3.8")),
        "confidence": Rate(Decimal("0.75")),
        "valid_until": GENERATED_AT + timedelta(days=1),
    }
    values.update(overrides)
    return RecommendationPlan(**values)


def recommendation_input(
    *,
    identifier: int = 1,
    disposition: RecommendationDisposition = RecommendationDisposition.RECOMMEND,
    selected_plan: RecommendationPlan | None | object = ...,
    generator_version: str = "v1",
    reason_codes: tuple[str, ...] = ("EXPECTED_VALUE_POSITIVE",),
    risk_codes: tuple[str, ...] = ("MARKET_VOLATILITY",),
    invalidation_codes: tuple[str, ...] = ("STOP_BREACH",),
) -> RecommendationInput:
    if selected_plan is ...:
        selected_plan = plan() if disposition.actionable else None
    return RecommendationInput(
        feature_snapshot_id=FeatureSnapshotID(UUID(int=identifier)),
        generator_code="RULE_ENGINE",
        generator_version=generator_version,
        disposition=disposition,
        plan=selected_plan,
        reason_codes=reason_codes,
        risk_codes=risk_codes,
        invalidation_codes=invalidation_codes,
    )
