"""Exact counterfactual price-only v2 eligibility from stored v1 snapshots."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from auto_trading_v2.application.contracts.training_readiness import (
    TrainingReadinessLineageRecord,
)
from auto_trading_v2.application.feature_building import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    PRICE_FEATURE_NAMES,
)
from auto_trading_v2.domain.training_readiness import (
    NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
    PRICE_ONLY_V2_INELIGIBILITY_REASON_ORDER,
    NamedCount,
    PercentageFact,
    PercentageStatus,
    calculate_percentage,
)

_VOLUME_REASONS = frozenset({"VOLUME_DATA_INCOMPLETE", "VOLUME_DATA_UNUSABLE"})


@dataclass(frozen=True, slots=True)
class PriceOnlyV2Analysis:
    price_feature_complete_count: int | str
    volume_only_degraded_count: int | str
    eligible_count: int | str
    ineligible_count: int | str
    ineligibility_reasons: tuple[NamedCount, ...]
    eligibility_percentage: PercentageFact
    eligible_rows: tuple[TrainingReadinessLineageRecord, ...]
    source_session_count_before: int
    source_session_count_after: int | str
    symbol_count_before: int
    symbol_count_after: int | str
    unavailable: bool


def analyze_price_only_v2(
    records: tuple[TrainingReadinessLineageRecord, ...],
) -> PriceOnlyV2Analysis:
    assessments = tuple(_assessment(row) for row in records)
    reasons = Counter(reason for _, _, _, reason in assessments if reason is not None)
    unavailable = any(eligible is None for eligible, _, _, _ in assessments)
    eligible_rows = tuple(
        row
        for row, (eligible, _, _, _) in zip(records, assessments, strict=True)
        if eligible is True
    )
    eligible_count = len(eligible_rows)
    return PriceOnlyV2Analysis(
        price_feature_complete_count=_derived(
            sum(complete is True for _, complete, _, _ in assessments), unavailable
        ),
        volume_only_degraded_count=_derived(
            sum(volume is True for _, _, volume, _ in assessments), unavailable
        ),
        eligible_count=_derived(eligible_count, unavailable),
        ineligible_count=_derived(
            sum(eligible is False for eligible, _, _, _ in assessments), unavailable
        ),
        ineligibility_reasons=tuple(
            NamedCount(code, reasons[code]) for code in PRICE_ONLY_V2_INELIGIBILITY_REASON_ORDER
        ),
        eligibility_percentage=_percentage(eligible_count, len(records), unavailable),
        eligible_rows=eligible_rows,
        source_session_count_before=len(
            {row.source_session_date for row in records if row.source_session_date is not None}
        ),
        source_session_count_after=_derived(
            len(
                {
                    row.source_session_date
                    for row in eligible_rows
                    if row.source_session_date is not None
                }
            ),
            unavailable,
        ),
        symbol_count_before=len({(row.mic_code, row.symbol.serialize()) for row in records}),
        symbol_count_after=_derived(
            len({(row.mic_code, row.symbol.serialize()) for row in eligible_rows}),
            unavailable,
        ),
        unavailable=unavailable,
    )


def _assessment(
    row: TrainingReadinessLineageRecord,
) -> tuple[bool | None, bool | None, bool | None, str | None]:
    if (
        row.feature_set_code is None
        or row.feature_set_version is None
        or row.feature_quality_status is None
    ):
        return None, None, None, "FEATURE_LINEAGE_UNAVAILABLE"
    if (row.feature_set_code, row.feature_set_version) != (
        FEATURE_SET_CODE,
        FEATURE_SET_VERSION,
    ):
        return False, False, False, "FEATURE_POLICY_NOT_V1"
    values = row.feature_values
    if values is None:
        return None, None, None, "FEATURE_LINEAGE_UNAVAILABLE"
    if any(name not in values for name in PRICE_FEATURE_NAMES):
        return False, False, False, "PRICE_FEATURE_MISSING"
    if any(not _is_canonical_decimal(values[name]) for name in PRICE_FEATURE_NAMES):
        return False, False, False, "PRICE_FEATURE_INVALID"
    if values.get("adjustment_basis") != "SPLIT_ADJUSTED":
        return False, True, False, "ADJUSTMENT_BASIS_INVALID"
    completed = values.get("completed_bar_count")
    if isinstance(completed, bool) or completed != 21:
        return False, True, False, "COMPLETED_BAR_COUNT_INVALID"
    reasons = frozenset(row.quality_reason_codes)
    if row.feature_quality_status == "READY":
        if reasons:
            return False, True, False, "QUALITY_REASON_INELIGIBLE"
        return True, True, False, None
    if row.feature_quality_status != "DEGRADED":
        return False, True, False, "QUALITY_STATUS_INELIGIBLE"
    if not reasons or not reasons.issubset(_VOLUME_REASONS):
        return False, True, False, "QUALITY_REASON_INELIGIBLE"
    return True, True, True, None


def _is_canonical_decimal(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return False
    if not parsed.is_finite():
        return False
    rendered = "0" if parsed == 0 else format(parsed, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return value == rendered


def _derived(count: int, unavailable: bool) -> int | str:
    return NOT_DERIVABLE_FROM_CURRENT_SCHEMA if unavailable else count


def _percentage(eligible: int, denominator: int, unavailable: bool) -> PercentageFact:
    if unavailable:
        return PercentageFact(
            NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
            NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
            None,
            PercentageStatus.NOT_DERIVABLE,
        )
    return calculate_percentage(eligible, denominator)
