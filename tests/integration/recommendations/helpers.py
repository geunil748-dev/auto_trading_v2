from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidRecommendationIDFactory
from auto_trading_v2.application.contracts.recommendations import (
    CreateRecommendationCommand,
    NewRecommendation,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import RecommendationCreationService
from auto_trading_v2.domain.feature_snapshots import FeatureSnapshot, TradingDayHorizon
from auto_trading_v2.domain.primitives import (
    Currency,
    IdentifierFactory,
    Price,
    Rate,
    RecommendationID,
)
from auto_trading_v2.domain.recommendations import (
    Recommendation,
    RecommendationDisposition,
    RecommendationPlan,
    recommendation_content_digest,
    recommendation_key,
)
from tests.integration.feature_snapshots.helpers import command as snapshot_command
from tests.integration.feature_snapshots.helpers import creation_service as snapshot_service


def persist_snapshot(
    unit_of_work_factory: UnitOfWorkFactory,
    case: int,
) -> FeatureSnapshot:
    return snapshot_service(unit_of_work_factory, case).create(snapshot_command(case)).snapshot


def command(
    snapshot: FeatureSnapshot,
    case: int,
    *,
    disposition: RecommendationDisposition = RecommendationDisposition.RECOMMEND,
    reason_codes: tuple[str, ...] = ("EXPECTED_VALUE_POSITIVE",),
) -> CreateRecommendationCommand:
    plan = (
        RecommendationPlan(
            currency=Currency("USD"),
            entry_price_low=Price(Decimal("100.123456789012345678")),
            entry_price_high=Price(Decimal("101.123456789012345678")),
            target_price=Price(Decimal("120.123456789012345678")),
            stop_price=Price(Decimal("95.123456789012345678")),
            expected_holding_trading_days=TradingDayHorizon(3),
            upside_probability=Rate(Decimal("0.650000000000000000")),
            target_probability=Rate(Decimal("0.550000000000000000")),
            stop_probability=Rate(Decimal("0.200000000000000000")),
            expected_value_rate=Rate(Decimal("0.120000000000000000")),
            reward_risk_ratio=Rate(Decimal("3.800000000000000000")),
            confidence=Rate(Decimal("0.750000000000000000")),
            valid_until=snapshot.snapshot_input.as_of + timedelta(days=2),
        )
        if disposition.actionable
        else None
    )
    return CreateRecommendationCommand(
        feature_snapshot_id=snapshot.feature_snapshot_id,
        generator_code=f"RULE_{case}",
        generator_version="v1",
        disposition=disposition,
        plan=plan,
        reason_codes=reason_codes,
        risk_codes=("MARKET_VOLATILITY",)
        if disposition.actionable or disposition is RecommendationDisposition.MARKET_RISK
        else (),
        invalidation_codes=("STOP_BREACH",) if disposition.actionable else (),
    )


def creation_service(
    unit_of_work_factory: UnitOfWorkFactory,
    snapshot: FeatureSnapshot,
    case: int,
) -> RecommendationCreationService:
    generated_at = snapshot.snapshot_input.as_of + timedelta(seconds=2)
    return RecommendationCreationService(
        unit_of_work_factory,
        FixedClock(generated_at),
        UuidRecommendationIDFactory(IdentifierFactory(lambda: UUID(int=1000 + case))),
    )


def new_recommendation(
    source: CreateRecommendationCommand,
    snapshot: FeatureSnapshot,
    case: int,
) -> NewRecommendation:
    recommendation_input = source.recommendation_input
    return NewRecommendation(
        recommendation_id=RecommendationID(UUID(int=2000 + case)),
        recommendation_key=recommendation_key(recommendation_input),
        content_digest=recommendation_content_digest(recommendation_input),
        recommendation_input=recommendation_input,
        generated_at=snapshot.snapshot_input.as_of + timedelta(seconds=2),
    )


def assert_same_recommendation(actual: Recommendation, expected: Recommendation) -> None:
    assert actual.recommendation_id == expected.recommendation_id
    assert actual.recommendation_key == expected.recommendation_key
    assert actual.content_digest == expected.content_digest
    assert actual.recommendation_input == expected.recommendation_input
    assert actual.generated_at == expected.generated_at
    assert actual.recorded_at == expected.recorded_at
    assert actual.generated_at.utcoffset() == timedelta(0)
    assert actual.recorded_at.utcoffset() == timedelta(0)


def row_for(
    source: CreateRecommendationCommand,
    snapshot: FeatureSnapshot,
    case: int,
) -> dict[str, object]:
    recommendation = new_recommendation(source, snapshot, case)
    content = recommendation.recommendation_input
    plan = content.plan
    return {
        "recommendation_id": recommendation.recommendation_id.value,
        "recommendation_key": recommendation.recommendation_key,
        "content_digest": recommendation.content_digest,
        "feature_snapshot_id": content.feature_snapshot_id.value,
        "generator_code": content.generator_code,
        "generator_version": content.generator_version,
        "disposition": content.disposition.value,
        "currency": None if plan is None else plan.currency.code,
        "entry_price_low": None if plan is None else plan.entry_price_low.value,
        "entry_price_high": None if plan is None else plan.entry_price_high.value,
        "target_price": None if plan is None else plan.target_price.value,
        "stop_price": None if plan is None else plan.stop_price.value,
        "expected_holding_trading_days": (
            None if plan is None else plan.expected_holding_trading_days.value
        ),
        "upside_probability": None if plan is None else plan.upside_probability.value,
        "target_probability": None if plan is None else plan.target_probability.value,
        "stop_probability": None if plan is None else plan.stop_probability.value,
        "expected_value_rate": None if plan is None else plan.expected_value_rate.value,
        "reward_risk_ratio": None if plan is None else plan.reward_risk_ratio.value,
        "confidence": None if plan is None else plan.confidence.value,
        "valid_until": None if plan is None else plan.valid_until,
        "reason_codes": '["EXPECTED_VALUE_POSITIVE"]',
        "risk_codes": (
            '["MARKET_VOLATILITY"]'
            if content.disposition.actionable
            or content.disposition is RecommendationDisposition.MARKET_RISK
            else "[]"
        ),
        "invalidation_codes": ('["STOP_BREACH"]' if content.disposition.actionable else "[]"),
        "generated_at": recommendation.generated_at,
    }
