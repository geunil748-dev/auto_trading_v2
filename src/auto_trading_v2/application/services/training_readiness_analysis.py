"""Pure application-level analysis of canonical upstream lineage rows."""

from collections import Counter, defaultdict

from auto_trading_v2.application.contracts.training_readiness import (
    TrainingReadinessLineageRecord,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
)
from auto_trading_v2.domain.primitives import DailyFeatureScoringItemID
from auto_trading_v2.domain.training_readiness import (
    COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE,
    EXCLUSION_REASON_ORDER,
    NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
    DataQualityDecisionEvidence,
    DatasetIdentityFacts,
    NamedCount,
    ProviderQualityDistribution,
    UpstreamQualityFacts,
    calculate_percentage,
)

_SCORED = frozenset({"SCORED_READY", "SCORED_DEGRADED"})


def dataset_identity_facts(dataset: ProbabilityCalibrationDataset) -> DatasetIdentityFacts:
    identity = dataset.identity
    return DatasetIdentityFacts(
        probability_calibration_dataset_id=(dataset.probability_calibration_dataset_id.serialize()),
        dataset_key=dataset.dataset_key,
        content_digest=dataset.content_digest,
        status=dataset.status.value,
        dataset_as_of=identity.dataset_as_of,
        generated_at=dataset.generated_at,
        horizon_trading_days=identity.horizon.value,
        dataset_policy_code=identity.dataset_policy_code.value,
        dataset_policy_version=identity.dataset_policy_version.value,
        label_policy_code=identity.label_policy_code.value,
        label_policy_version=identity.label_policy_version.value,
        outcome_policy_code=identity.outcome_policy_code.value,
        outcome_policy_version=identity.outcome_policy_version.value,
        scoring_policy_code=identity.scoring_policy_code.value,
        scoring_policy_version=identity.scoring_policy_version.value,
        ranking_policy_code=identity.ranking_policy_code.value,
        ranking_policy_version=identity.ranking_policy_version.value,
        provider_code=identity.provider_code,
        calendar_code=identity.calendar_code.value,
        calendar_version=identity.calendar_version.value,
    )


def analyze_upstream_lineage(
    dataset: ProbabilityCalibrationDataset,
    items: tuple[ProbabilityCalibrationDatasetItem, ...],
    records: tuple[TrainingReadinessLineageRecord, ...],
) -> tuple[UpstreamQualityFacts, DataQualityDecisionEvidence, tuple[str, ...]]:
    included = {item.source_daily_feature_scoring_item_id for item in items}
    reasons = Counter[str]()
    for record in records:
        reason = _exclusion_reason(dataset, record, included)
        if reason is not None:
            reasons[reason] += 1
    provider_rows: dict[str, list[TrainingReadinessLineageRecord]] = defaultdict(list)
    for record in records:
        provider_rows[record.provider_code].append(record)
    distributions = tuple(
        _provider_distribution(provider, tuple(rows), included)
        for provider, rows in sorted(provider_rows.items())
    )
    volume_count = sum("VOLUME_DATA_INCOMPLETE" in row.quality_reason_codes for row in records)
    policy_mismatch = sum(_scoring_policy_mismatch(dataset, row) for row in records) + sum(
        row.has_calendar_outcome and not row.has_policy_outcome for row in records
    )
    provider_mismatch = sum(
        row.has_as_of_outcome and not row.has_provider_outcome for row in records
    )
    calendar_mismatch = sum(
        row.has_provider_outcome and not row.has_calendar_outcome for row in records
    )
    missing_outcome = sum(not row.has_any_outcome for row in records)
    missing_as_of = sum(row.has_any_outcome and not row.has_as_of_outcome for row in records)
    missing_label = sum(row.has_policy_outcome and not row.has_any_label for row in records)
    upstream = UpstreamQualityFacts(
        source_scoring_item_count=len(records),
        scored_ready_count=sum(row.scoring_outcome == "SCORED_READY" for row in records),
        scored_degraded_count=sum(row.scoring_outcome == "SCORED_DEGRADED" for row in records),
        skipped_failed_count=sum(row.scoring_outcome not in _SCORED for row in records),
        source_feature_snapshot_ready_count=sum(
            row.feature_quality_status == "READY" for row in records
        ),
        source_feature_snapshot_degraded_count=sum(
            row.feature_quality_status == "DEGRADED" for row in records
        ),
        source_feature_snapshot_data_insufficient_count=NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
        volume_data_incomplete_count=volume_count,
        missing_outcome_count=missing_outcome,
        missing_as_of_eligible_outcome_count=missing_as_of,
        missing_label_count=missing_label,
        policy_mismatch_count=policy_mismatch,
        provider_mismatch_count=provider_mismatch,
        calendar_mismatch_count=calendar_mismatch,
        other_exclusion_count=reasons["OTHER_CONTRACT_FAILURE"],
        exclusion_reason_counts=tuple(
            NamedCount(code, reasons[code]) for code in EXCLUSION_REASON_ORDER
        ),
    )
    included_records = sum(row.source_daily_feature_scoring_item_id in included for row in records)
    complete_volume = sum(
        row.feature_quality_status == "READY"
        and "VOLUME_DATA_INCOMPLETE" not in row.quality_reason_codes
        for row in records
    )
    decision = DataQualityDecisionEvidence(
        volume_only_excluded=calculate_percentage(reasons["VOLUME_DATA_INCOMPLETE"], len(records)),
        price_only_eligibility=(COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE),
        complete_volume=calculate_percentage(complete_volume, len(records)),
        provider_quality_distribution=distributions,
        horizon_included_count=included_records,
        horizon_excluded_count=len(records) - included_records,
        source_session_count_before_ready_filter=len(
            {row.source_session_date for row in records if row.source_session_date is not None}
        ),
        source_session_count_after_ready_filter=len({item.source_session_date for item in items}),
        symbol_count_before_ready_filter=len(
            {(row.mic_code, row.symbol.serialize()) for row in records}
        ),
        symbol_count_after_ready_filter=len(
            {(item.mic_code, item.symbol.serialize()) for item in items}
        ),
    )
    not_derivable = (
        "source_feature_snapshot_data_insufficient_count",
        "would_otherwise_satisfy_price_feature_quality_count",
        "counterfactual_price_only_eligibility_percentage",
    )
    return upstream, decision, not_derivable


def _exclusion_reason(
    dataset: ProbabilityCalibrationDataset,
    row: TrainingReadinessLineageRecord,
    included: set[DailyFeatureScoringItemID],
) -> str | None:
    if row.source_daily_feature_scoring_item_id in included:
        return None
    if _scoring_policy_mismatch(dataset, row):
        return "OTHER_CONTRACT_FAILURE"
    if row.scoring_outcome != "SCORED_READY":
        if "VOLUME_DATA_INCOMPLETE" in row.quality_reason_codes:
            return "VOLUME_DATA_INCOMPLETE"
        if row.source_quality_status != "READY" or row.feature_quality_status != "READY":
            return "FEATURE_QUALITY_NOT_READY"
        return "SCORE_NOT_READY"
    if row.overall_relative_score is None or row.source_rank is None:
        return "MISSING_SCORE"
    if not row.has_any_outcome:
        return "OUTCOME_NOT_FOUND"
    if not row.has_as_of_outcome:
        return "OUTCOME_NOT_AVAILABLE_AS_OF"
    if not row.has_provider_outcome:
        return "PROVIDER_MISMATCH"
    if not row.has_calendar_outcome:
        return "CALENDAR_MISMATCH"
    if not row.has_policy_outcome:
        return "OUTCOME_POLICY_MISMATCH"
    if not row.has_any_label:
        return "LABEL_NOT_FOUND"
    if not row.has_matching_label:
        return "LABEL_POLICY_MISMATCH"
    return "OTHER_CONTRACT_FAILURE"


def _scoring_policy_mismatch(
    dataset: ProbabilityCalibrationDataset, row: TrainingReadinessLineageRecord
) -> bool:
    identity = dataset.identity
    return (
        row.scoring_policy_code,
        row.scoring_policy_version,
        row.ranking_policy_code,
        row.ranking_policy_version,
    ) != (
        identity.scoring_policy_code.value,
        identity.scoring_policy_version.value,
        identity.ranking_policy_code.value,
        identity.ranking_policy_version.value,
    )


def _provider_distribution(
    provider_code: str,
    rows: tuple[TrainingReadinessLineageRecord, ...],
    included: set[DailyFeatureScoringItemID],
) -> ProviderQualityDistribution:
    return ProviderQualityDistribution(
        provider_code=provider_code,
        total_count=len(rows),
        ready_count=sum(row.feature_quality_status == "READY" for row in rows),
        degraded_count=sum(row.feature_quality_status == "DEGRADED" for row in rows),
        data_insufficient_count=sum(row.pipeline_outcome == "DATA_INSUFFICIENT" for row in rows),
        volume_incomplete_count=sum(
            "VOLUME_DATA_INCOMPLETE" in row.quality_reason_codes for row in rows
        ),
        included_count=sum(row.source_daily_feature_scoring_item_id in included for row in rows),
    )
