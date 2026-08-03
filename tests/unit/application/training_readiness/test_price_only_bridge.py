from dataclasses import replace

from auto_trading_v2.application.feature_building import PRICE_FEATURE_NAMES
from auto_trading_v2.application.services.training_readiness_price_only import (
    analyze_price_only_v2,
)
from auto_trading_v2.domain.training_readiness import (
    NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
    PercentageStatus,
)
from tests.unit.training_readiness_helpers import aggregate, lineage_record


def _record(**changes: object) -> object:
    source = lineage_record(aggregate().items[0])
    return replace(source, **changes)


def _reasons(result: object) -> dict[str, int | str]:
    return {fact.code: fact.count for fact in result.ineligibility_reasons}


def test_ready_and_volume_only_v1_snapshots_are_exactly_eligible() -> None:
    ready = _record()
    incomplete = _record(
        feature_quality_status="DEGRADED",
        quality_reason_codes=("VOLUME_DATA_INCOMPLETE",),
    )
    unusable = _record(
        feature_quality_status="DEGRADED",
        quality_reason_codes=("VOLUME_DATA_UNUSABLE",),
    )

    result = analyze_price_only_v2((ready, incomplete, unusable))

    assert result.price_feature_complete_count == 3
    assert result.volume_only_degraded_count == 2
    assert result.eligible_count == 3
    assert result.ineligible_count == 0
    assert result.eligibility_percentage.percentage == "100.000000"
    assert result.symbol_count_before == result.symbol_count_after == 1
    assert result.source_session_count_before == result.source_session_count_after == 1


def test_non_volume_reason_missing_null_invalid_and_wrong_policy_are_ineligible() -> None:
    baseline = _record()
    values = dict(baseline.feature_values)
    missing = dict(values)
    missing.pop(PRICE_FEATURE_NAMES[0])
    null = dict(values, last_close=None)
    invalid = dict(values, last_close="NaN")
    rows = (
        replace(
            baseline,
            feature_quality_status="DEGRADED",
            quality_reason_codes=("VOLUME_DATA_INCOMPLETE", "OTHER_REASON"),
        ),
        replace(baseline, feature_values=missing),
        replace(baseline, feature_values=null),
        replace(baseline, feature_values=invalid),
        replace(baseline, feature_set_version="v2"),
    )

    result = analyze_price_only_v2(rows)
    reasons = _reasons(result)

    assert result.eligible_count == 0
    assert result.ineligible_count == 5
    assert reasons["QUALITY_REASON_INELIGIBLE"] == 1
    assert reasons["PRICE_FEATURE_MISSING"] == 1
    assert reasons["PRICE_FEATURE_INVALID"] == 2
    assert reasons["FEATURE_POLICY_NOT_V1"] == 1


def test_unavailable_lineage_is_not_zero_and_empty_denominator_is_explicit() -> None:
    unavailable = _record(feature_values=None)

    unknown = analyze_price_only_v2((unavailable,))
    empty = analyze_price_only_v2(())

    assert unknown.eligible_count == NOT_DERIVABLE_FROM_CURRENT_SCHEMA
    assert unknown.ineligible_count == NOT_DERIVABLE_FROM_CURRENT_SCHEMA
    assert unknown.eligibility_percentage.status is PercentageStatus.NOT_DERIVABLE
    assert _reasons(unknown)["FEATURE_LINEAGE_UNAVAILABLE"] == 1
    assert empty.eligible_count == empty.ineligible_count == 0
    assert empty.eligibility_percentage.status is PercentageStatus.ZERO_DENOMINATOR
