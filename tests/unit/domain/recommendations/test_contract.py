from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import Currency, Price, Rate
from auto_trading_v2.domain.recommendations import (
    RecommendationDisposition,
    RecommendationInput,
    RecommendationValidationError,
    recommendation_content_digest,
    recommendation_key,
    validate_generated_at,
)
from tests.unit.domain.recommendations.helpers import (
    GENERATED_AT,
    plan,
    recommendation_input,
)


def test_all_six_dispositions_and_actionability_are_explicit() -> None:
    assert {item.value for item in RecommendationDisposition} == {
        "RECOMMEND",
        "CONDITIONAL",
        "WATCH",
        "NO_RECOMMENDATION",
        "DATA_INSUFFICIENT",
        "MARKET_RISK",
    }
    assert {item for item in RecommendationDisposition if item.actionable} == {
        RecommendationDisposition.RECOMMEND,
        RecommendationDisposition.CONDITIONAL,
    }
    with pytest.raises(ValueError):
        RecommendationDisposition("UNKNOWN")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entry_price_low", Price(Decimal("95"))),
        ("entry_price_high", Price(Decimal("121"))),
        ("target_price", Price(Decimal("101"))),
        ("stop_price", Price(Decimal("100"))),
        ("upside_probability", Rate(Decimal("-0.1"))),
        ("target_probability", Rate(Decimal("1.1"))),
        ("expected_value_rate", Rate(Decimal("0"))),
        ("reward_risk_ratio", Rate(Decimal("-1"))),
        ("confidence", Rate(Decimal("1.1"))),
    ],
)
def test_invalid_plan_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(RecommendationValidationError):
        plan(**{field: value})


def test_probability_sum_holding_and_timestamp_rules_are_rejected() -> None:
    with pytest.raises(RecommendationValidationError):
        plan(
            target_probability=Rate(Decimal("0.8")),
            stop_probability=Rate(Decimal("0.3")),
        )
    with pytest.raises(ValidationError):
        TradingDayHorizon(0)
    with pytest.raises(ValidationError):
        TradingDayHorizon(6)
    with pytest.raises(RecommendationValidationError):
        plan(valid_until=datetime(2026, 7, 29))
    with pytest.raises(RecommendationValidationError):
        validate_generated_at(recommendation_input(), GENERATED_AT + timedelta(days=1))


@pytest.mark.parametrize("value", [0.1, float("nan"), float("inf")])
def test_python_float_never_enters_official_numbers(value: float) -> None:
    with pytest.raises(ValidationError):
        Price(value)
    with pytest.raises(ValidationError):
        Rate(value)


def test_actionable_and_non_actionable_shapes_are_strict() -> None:
    with pytest.raises(RecommendationValidationError):
        recommendation_input(selected_plan=None)
    with pytest.raises(RecommendationValidationError):
        recommendation_input(
            disposition=RecommendationDisposition.WATCH,
            selected_plan=plan(),
            risk_codes=(),
            invalidation_codes=(),
        )
    for disposition in (
        RecommendationDisposition.WATCH,
        RecommendationDisposition.NO_RECOMMENDATION,
        RecommendationDisposition.DATA_INSUFFICIENT,
    ):
        result = recommendation_input(
            disposition=disposition,
            risk_codes=(),
            invalidation_codes=(),
        )
        assert result.plan is None


def test_reason_risk_invalidation_code_contract_is_canonical_and_safe() -> None:
    value = recommendation_input(
        reason_codes=("SECOND_REASON", "FIRST_REASON"),
        risk_codes=("SECOND_RISK", "FIRST_RISK"),
        invalidation_codes=("SECOND_INVALIDATION", "FIRST_INVALIDATION"),
    )
    assert value.reason_codes == ("FIRST_REASON", "SECOND_REASON")
    assert value.risk_codes == ("FIRST_RISK", "SECOND_RISK")
    assert value.invalidation_codes == ("FIRST_INVALIDATION", "SECOND_INVALIDATION")
    for changes in (
        {"reason_codes": ()},
        {"risk_codes": ()},
        {"invalidation_codes": ()},
        {"reason_codes": ("DUPLICATE", "DUPLICATE")},
        {"reason_codes": ("lowercase",)},
    ):
        with pytest.raises(RecommendationValidationError):
            recommendation_input(**changes)
    with pytest.raises(RecommendationValidationError):
        recommendation_input(
            disposition=RecommendationDisposition.MARKET_RISK,
            risk_codes=(),
            invalidation_codes=(),
        )
    with pytest.raises(RecommendationValidationError):
        recommendation_input(
            disposition=RecommendationDisposition.WATCH,
            risk_codes=(),
            invalidation_codes=("NOT_ALLOWED",),
        )


def test_identity_and_content_digest_have_separate_canonical_inputs() -> None:
    source = recommendation_input(
        reason_codes=("SECOND_REASON", "FIRST_REASON"),
        risk_codes=("SECOND_RISK", "FIRST_RISK"),
        invalidation_codes=("SECOND_INVALIDATION", "FIRST_INVALIDATION"),
    )
    reordered = recommendation_input(
        reason_codes=("FIRST_REASON", "SECOND_REASON"),
        risk_codes=("FIRST_RISK", "SECOND_RISK"),
        invalidation_codes=("FIRST_INVALIDATION", "SECOND_INVALIDATION"),
        selected_plan=replace(
            plan(),
            entry_price_low=Price(Decimal("100.000")),
            expected_value_rate=Rate(Decimal("0.1200")),
        ),
    )
    assert recommendation_key(source) == recommendation_key(reordered)
    assert len(recommendation_key(source)) == 82
    assert recommendation_content_digest(source) == recommendation_content_digest(reordered)
    assert recommendation_key(source) != recommendation_key(
        recommendation_input(generator_version="v2")
    )
    assert recommendation_key(source) != recommendation_key(recommendation_input(identifier=2))
    assert recommendation_content_digest(source) != recommendation_content_digest(
        recommendation_input(reason_codes=("OTHER_REASON",))
    )


def test_wrong_types_and_non_usd_are_rejected() -> None:
    with pytest.raises(RecommendationValidationError):
        plan(currency=Currency("KRW"))
    with pytest.raises(RecommendationValidationError):
        RecommendationInput(
            feature_snapshot_id=object(),
            generator_code="RULE",
            generator_version="v1",
            disposition=RecommendationDisposition.WATCH,
            plan=None,
            reason_codes=("REASON",),
        )
