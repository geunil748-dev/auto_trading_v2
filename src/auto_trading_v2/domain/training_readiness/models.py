"""Immutable result contracts for one read-only training-readiness audit."""

from dataclasses import dataclass
from datetime import date, datetime

from auto_trading_v2.domain.training_readiness.outcomes import (
    LegacyCalibrationReadiness,
    MvpTradeModelReadiness,
    PercentageStatus,
)

DerivableCount = int | str


@dataclass(frozen=True, slots=True)
class NamedCount:
    code: str
    count: DerivableCount


@dataclass(frozen=True, slots=True)
class PercentageFact:
    count: DerivableCount
    denominator: DerivableCount
    percentage: str | None
    status: PercentageStatus


@dataclass(frozen=True, slots=True)
class DatasetIdentityFacts:
    probability_calibration_dataset_id: str
    dataset_key: str
    content_digest: str
    status: str
    dataset_as_of: datetime
    generated_at: datetime
    horizon_trading_days: int
    dataset_policy_code: str
    dataset_policy_version: str
    label_policy_code: str
    label_policy_version: str
    outcome_policy_code: str
    outcome_policy_version: str
    scoring_policy_code: str
    scoring_policy_version: str
    ranking_policy_code: str
    ranking_policy_version: str
    provider_code: str
    calendar_code: str
    calendar_version: str


@dataclass(frozen=True, slots=True)
class IncludedDatasetFacts:
    total_item_count: int
    unique_source_session_count: int
    unique_symbol_listing_count: int
    earliest_source_session: date | None
    latest_source_session: date | None
    date_span_days: int
    retrospective_replay_item_count: int
    retrospective_replay_source_session_count: int
    prospective_item_count: int
    prospective_source_session_count: int
    positive_count: int
    not_positive_count: int
    replay_positive_count: int
    replay_not_positive_count: int
    prospective_positive_count: int
    prospective_not_positive_count: int
    null_score_count: int
    invalid_score_count: int
    duplicate_source_item_count: int
    canonical_order_valid: bool
    item_content_digest_valid: bool


@dataclass(frozen=True, slots=True)
class UpstreamQualityFacts:
    source_scoring_item_count: int
    scored_ready_count: int
    scored_degraded_count: int
    skipped_failed_count: int
    source_feature_snapshot_ready_count: int
    source_feature_snapshot_degraded_count: int
    source_feature_snapshot_data_insufficient_count: DerivableCount
    volume_data_incomplete_count: int
    price_feature_complete_count: DerivableCount
    volume_only_degraded_count: DerivableCount
    price_only_v2_eligible_count: DerivableCount
    price_only_v2_ineligible_count: DerivableCount
    price_only_v2_ineligibility_reason_counts: tuple[NamedCount, ...]
    missing_outcome_count: int
    missing_as_of_eligible_outcome_count: int
    missing_label_count: int
    policy_mismatch_count: int
    provider_mismatch_count: int
    calendar_mismatch_count: int
    other_exclusion_count: int
    exclusion_reason_counts: tuple[NamedCount, ...]


@dataclass(frozen=True, slots=True)
class ProviderQualityDistribution:
    provider_code: str
    total_count: int
    ready_count: int
    degraded_count: int
    data_insufficient_count: int
    volume_incomplete_count: int
    included_count: int


@dataclass(frozen=True, slots=True)
class DataQualityDecisionEvidence:
    volume_only_excluded: PercentageFact
    price_only_eligibility: PercentageFact
    complete_volume: PercentageFact
    provider_quality_distribution: tuple[ProviderQualityDistribution, ...]
    horizon_included_count: int
    horizon_excluded_count: int
    source_session_count_before_ready_filter: int
    source_session_count_after_ready_filter: int
    symbol_count_before_ready_filter: int
    symbol_count_after_ready_filter: int
    price_only_source_session_count_before_eligibility: int
    price_only_source_session_count_after_eligibility: DerivableCount
    price_only_symbol_count_before_eligibility: int
    price_only_symbol_count_after_eligibility: DerivableCount


@dataclass(frozen=True, slots=True)
class LegacyCalibrationReadinessResult:
    status: LegacyCalibrationReadiness
    blockers: tuple[str, ...]
    limitation: str


@dataclass(frozen=True, slots=True)
class MvpTradeModelReadinessResult:
    status: MvpTradeModelReadiness
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrainingReadinessAuditResult:
    audit_generated_at: datetime
    dataset_identity: DatasetIdentityFacts
    included_dataset: IncludedDatasetFacts
    upstream_quality: UpstreamQualityFacts
    legacy_calibration_readiness: LegacyCalibrationReadinessResult
    mvp_trade_model_readiness: MvpTradeModelReadinessResult
    data_quality_decision_evidence: DataQualityDecisionEvidence
    not_derivable_fields: tuple[str, ...]
    conclusion: str


@dataclass(frozen=True, slots=True)
class HorizonAuditGroup:
    horizon_trading_days: int
    dataset_ids: tuple[str, ...]
    included_count: int
    excluded_count: int


@dataclass(frozen=True, slots=True)
class TrainingReadinessAuditBatchResult:
    audit_generated_at: datetime
    audits: tuple[TrainingReadinessAuditResult, ...]
    horizon_groups: tuple[HorizonAuditGroup, ...]
