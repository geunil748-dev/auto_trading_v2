"""Pure deterministic calculations for included P4B.2A dataset items."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
    ProbabilityCalibrationDatasetStatus,
    calibration_dataset_content_digest,
    dataset_item_order_key,
)
from auto_trading_v2.domain.feature_outcomes import OutcomeObservationMode
from auto_trading_v2.domain.outcome_labels import PositiveForwardCloseLabel
from auto_trading_v2.domain.training_readiness.models import (
    IncludedDatasetFacts,
    LegacyCalibrationReadinessResult,
    PercentageFact,
)
from auto_trading_v2.domain.training_readiness.outcomes import (
    LEGACY_RESEARCH_LIMITATION,
    LegacyCalibrationReadiness,
    PercentageStatus,
)


def calculate_percentage(count: int, denominator: int) -> PercentageFact:
    if count < 0 or denominator < 0 or count > denominator:
        raise ValueError("percentage inputs are invalid")
    if denominator == 0:
        return PercentageFact(count, denominator, None, PercentageStatus.ZERO_DENOMINATOR)
    with localcontext() as context:
        context.prec = 28
        percentage = (Decimal(count) * Decimal(100) / Decimal(denominator)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_EVEN
        )
    return PercentageFact(count, denominator, format(percentage, "f"), PercentageStatus.DERIVED)


def included_dataset_facts(
    dataset: ProbabilityCalibrationDataset,
    items: tuple[ProbabilityCalibrationDatasetItem, ...],
) -> IncludedDatasetFacts:
    replay = tuple(
        item
        for item in items
        if item.observation_mode is OutcomeObservationMode.RETROSPECTIVE_REPLAY
    )
    prospective = tuple(
        item for item in items if item.observation_mode is OutcomeObservationMode.PROSPECTIVE
    )
    sessions = {item.source_session_date.value for item in items}
    symbols = {(item.mic_code, item.symbol.serialize()) for item in items}
    ordered_dates = sorted(sessions)
    score_values = tuple(item.overall_relative_score.value for item in items)
    source_ids = tuple(item.source_daily_feature_scoring_item_id for item in items)
    canonical_order = items == tuple(sorted(items, key=dataset_item_order_key)) and tuple(
        item.ordinal for item in items
    ) == tuple(range(1, len(items) + 1))
    try:
        digest_valid = dataset.content_digest == calibration_dataset_content_digest(dataset, items)
    except (TypeError, ValueError):
        digest_valid = False
    return IncludedDatasetFacts(
        total_item_count=len(items),
        unique_source_session_count=len(sessions),
        unique_symbol_listing_count=len(symbols),
        earliest_source_session=None if not ordered_dates else ordered_dates[0],
        latest_source_session=None if not ordered_dates else ordered_dates[-1],
        date_span_days=(
            0 if len(ordered_dates) < 2 else (ordered_dates[-1] - ordered_dates[0]).days
        ),
        retrospective_replay_item_count=len(replay),
        retrospective_replay_source_session_count=len(
            {item.source_session_date for item in replay}
        ),
        prospective_item_count=len(prospective),
        prospective_source_session_count=len({item.source_session_date for item in prospective}),
        positive_count=sum(
            item.label_value is PositiveForwardCloseLabel.POSITIVE for item in items
        ),
        not_positive_count=sum(
            item.label_value is PositiveForwardCloseLabel.NOT_POSITIVE for item in items
        ),
        replay_positive_count=sum(
            item.label_value is PositiveForwardCloseLabel.POSITIVE for item in replay
        ),
        replay_not_positive_count=sum(
            item.label_value is PositiveForwardCloseLabel.NOT_POSITIVE for item in replay
        ),
        prospective_positive_count=sum(
            item.label_value is PositiveForwardCloseLabel.POSITIVE for item in prospective
        ),
        prospective_not_positive_count=sum(
            item.label_value is PositiveForwardCloseLabel.NOT_POSITIVE for item in prospective
        ),
        null_score_count=0,
        invalid_score_count=sum(value < 0 or value > 100 for value in score_values),
        duplicate_source_item_count=len(source_ids) - len(set(source_ids)),
        canonical_order_valid=canonical_order,
        item_content_digest_valid=digest_valid,
    )


def evaluate_legacy_calibration_readiness(
    dataset: ProbabilityCalibrationDataset,
    facts: IncludedDatasetFacts,
) -> LegacyCalibrationReadinessResult:
    blockers: list[str] = []
    if (
        dataset.status
        not in {
            ProbabilityCalibrationDatasetStatus.READY,
            ProbabilityCalibrationDatasetStatus.EMPTY,
        }
        or not facts.canonical_order_valid
        or not facts.item_content_digest_valid
        or facts.null_score_count
        or facts.invalid_score_count
        or facts.duplicate_source_item_count
    ):
        blockers.append("LEGACY_SOURCE_CONTRACT_INVALID")
        status = LegacyCalibrationReadiness.SOURCE_INELIGIBLE
    elif (
        facts.total_item_count < 300
        or facts.unique_source_session_count < 60
        or facts.retrospective_replay_item_count < 150
        or facts.retrospective_replay_source_session_count < 20
    ):
        blockers.append("LEGACY_SAMPLE_OR_SESSION_THRESHOLD_NOT_MET")
        status = LegacyCalibrationReadiness.DATA_INSUFFICIENT
    elif (
        facts.positive_count < 60
        or facts.not_positive_count < 60
        or facts.replay_positive_count < 30
        or facts.replay_not_positive_count < 30
    ):
        blockers.append("LEGACY_CLASS_THRESHOLD_NOT_MET")
        status = LegacyCalibrationReadiness.CLASS_IMBALANCED
    elif (
        facts.prospective_item_count < 100
        or facts.prospective_source_session_count < 20
        or facts.prospective_positive_count < 20
        or facts.prospective_not_positive_count < 20
    ):
        blockers.append("LEGACY_PROSPECTIVE_THRESHOLD_NOT_MET")
        status = LegacyCalibrationReadiness.PROSPECTIVE_INSUFFICIENT
    else:
        status = LegacyCalibrationReadiness.DATA_READY
    return LegacyCalibrationReadinessResult(status, tuple(blockers), LEGACY_RESEARCH_LIMITATION)
