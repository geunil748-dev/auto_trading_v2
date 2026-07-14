"""Stable immutable built-in filter-set definitions."""

from decimal import Decimal
from uuid import UUID

from auto_trading_v2.domain.filtering.models import (
    CHECK_ORDER,
    FilterCheckName,
    FilterCheckWeight,
    FilterMode,
    FilterSetDefinition,
    FilterSetName,
    FilterThresholds,
)
from auto_trading_v2.domain.primitives import FilterSetID, Price

EVALUATION_VERSION = "v1"

COMMON_THRESHOLDS = FilterThresholds(
    minimum_price=Price(Decimal("10")),
    maximum_price=Price(Decimal("300")),
    minimum_opening_change=Decimal("0.03"),
    maximum_entry_change=Decimal("0.15"),
    breakout_factor=Decimal("0.5"),
)

COMMON_WEIGHTS = tuple(
    FilterCheckWeight(name, weight)
    for name, weight in zip(
        CHECK_ORDER,
        (Decimal("20"), Decimal("20"), Decimal("20"), Decimal("30"), Decimal("10")),
        strict=True,
    )
)

STRICT = FilterSetDefinition(
    filter_set_id=FilterSetID(UUID("aaad2a67-4080-5805-90d5-2b6c350b8cdd")),
    name=FilterSetName.STRICT,
    evaluation_version=EVALUATION_VERSION,
    mode=FilterMode.STRICT,
    thresholds=COMMON_THRESHOLDS,
    weights=COMMON_WEIGHTS,
    hard_checks=CHECK_ORDER,
    minimum_score=Decimal("100"),
)

BALANCED = FilterSetDefinition(
    filter_set_id=FilterSetID(UUID("58865908-eb8a-5089-bc66-b38b49578f84")),
    name=FilterSetName.BALANCED,
    evaluation_version=EVALUATION_VERSION,
    mode=FilterMode.BALANCED,
    thresholds=COMMON_THRESHOLDS,
    weights=COMMON_WEIGHTS,
    hard_checks=(FilterCheckName.PRICE_RANGE, FilterCheckName.ENTRY_CHANGE_MAX),
    minimum_score=Decimal("70"),
)

SCORE_ONLY = FilterSetDefinition(
    filter_set_id=FilterSetID(UUID("e5f2aa3d-82e1-566a-aeb4-7313b49fc436")),
    name=FilterSetName.SCORE_ONLY,
    evaluation_version=EVALUATION_VERSION,
    mode=FilterMode.SCORE_ONLY,
    thresholds=COMMON_THRESHOLDS,
    weights=COMMON_WEIGHTS,
    hard_checks=(),
    minimum_score=Decimal("60"),
)

OBSERVATION = FilterSetDefinition(
    filter_set_id=FilterSetID(UUID("bf66c976-b971-571e-b688-d21abfacfb4d")),
    name=FilterSetName.OBSERVATION,
    evaluation_version=EVALUATION_VERSION,
    mode=FilterMode.OBSERVATION,
    thresholds=COMMON_THRESHOLDS,
    weights=COMMON_WEIGHTS,
    hard_checks=(),
    minimum_score=Decimal("0"),
)

BUILT_IN_FILTER_SETS = (STRICT, BALANCED, SCORE_ONLY, OBSERVATION)
