"""Source-chain validation and immutable P4B.1 outcome construction."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast

from auto_trading_v2.application.services.daily_feature_outcome_digest import (
    outcome_content_payload,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    SOURCE_PROVIDER_CODE,
    CalculatedForwardOutcome,
    DailyFeatureOutcome,
    DailyFeatureOutcomeIdentity,
    OutcomeObservationMode,
    daily_feature_outcome_key,
    fixed_outcome_policy_values,
    outcome_content_digest,
    path_revision_digest,
)
from auto_trading_v2.domain.feature_outcomes.values import canonical_outcome_price
from auto_trading_v2.domain.feature_pipeline import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    PIPELINE_CODE,
    PIPELINE_VERSION,
    DailyFeaturePipelineItem,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringItem,
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRun,
    FeatureScoringValidationError,
    parse_v1_technical_features,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, FeatureSnapshot
from auto_trading_v2.domain.market_calendar import MarketSession
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeID, SessionDate


@dataclass(frozen=True, slots=True)
class ValidatedOutcomeSource:
    pipeline: DailyFeaturePipelineRunWithItems
    pipeline_item: DailyFeaturePipelineItem
    snapshot: FeatureSnapshot
    reference_close: Decimal


def validate_outcome_source(
    scoring_run: DailyFeatureScoringRun,
    scoring_item: DailyFeatureScoringItem,
    pipeline: DailyFeaturePipelineRunWithItems | None,
    snapshot: FeatureSnapshot | None,
) -> ValidatedOutcomeSource | None:
    if pipeline is None or snapshot is None:
        return None
    source_run = pipeline.run
    identity = source_run.identity
    expected_identity = (
        PIPELINE_CODE,
        PIPELINE_VERSION,
        FEATURE_SET_CODE,
        FEATURE_SET_VERSION,
        SOURCE_PROVIDER_CODE,
        CALENDAR_CODE,
        CALENDAR_VERSION,
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
    )
    actual_identity = (
        identity.pipeline_code,
        identity.pipeline_version,
        identity.feature_set_code,
        identity.feature_set_version,
        identity.provider_code,
        identity.calendar_code.value,
        identity.calendar_version.value,
        identity.adjustment_basis,
    )
    if actual_identity != expected_identity or identity.completed_session_date is None:
        return None
    if scoring_run.identity.source_daily_feature_pipeline_run_id != (
        source_run.daily_feature_pipeline_run_id
    ):
        return None
    source_item = next(
        (
            item
            for item in pipeline.items
            if item.daily_feature_pipeline_item_id
            == scoring_item.source_daily_feature_pipeline_item_id
        ),
        None,
    )
    if source_item is None or not _matching_chain(scoring_item, source_item, snapshot):
        return None
    source = snapshot.snapshot_input
    if (
        source.feature_set_code != identity.feature_set_code
        or source.feature_set_version != identity.feature_set_version
        or source.horizon != identity.horizon
        or source.as_of != identity.as_of
        or source.symbol != scoring_item.symbol
        or source.quality_status != scoring_item.source_quality_status
        or source_item.completed_session_date != identity.completed_session_date
    ):
        return None
    try:
        reference = parse_v1_technical_features(snapshot).values["last_close"]
    except (FeatureScoringValidationError, KeyError):
        return None
    if not isinstance(reference, Decimal) or not reference.is_finite() or reference <= 0:
        return None
    reference_close = canonical_outcome_price(reference, "REFERENCE_CLOSE_INVALID")
    return ValidatedOutcomeSource(pipeline, source_item, snapshot, reference_close)


def future_sessions(
    sessions: tuple[MarketSession, ...],
    source_date: object,
    horizon: int,
) -> tuple[MarketSession, ...] | None:
    index = next(
        (
            position
            for position, session in enumerate(sessions)
            if session.session_date == source_date
        ),
        None,
    )
    if index is None:
        return None
    selected = sessions[index + 1 : index + 1 + horizon]
    return selected if len(selected) == horizon else ()


def build_daily_feature_outcome(
    outcome_id: DailyFeatureOutcomeID,
    scoring_run: DailyFeatureScoringRun,
    scoring_item: DailyFeatureScoringItem,
    source: ValidatedOutcomeSource,
    calculated: CalculatedForwardOutcome,
    observation_as_of: datetime,
    mode: OutcomeObservationMode,
    generated_at: datetime,
) -> DailyFeatureOutcome:
    pipeline_run = source.pipeline.run
    source_session_date = cast(SessionDate, pipeline_run.identity.completed_session_date)
    policy_code, policy_version = fixed_outcome_policy_values()
    path_digest = path_revision_digest(calculated.future_bar_provenance)
    outcome_identity = DailyFeatureOutcomeIdentity(
        scoring_item.daily_feature_scoring_item_id,
        policy_code,
        policy_version,
        pipeline_run.identity.horizon,
        path_digest,
    )
    common = {
        "calendar_code": pipeline_run.identity.calendar_code,
        "calendar_version": pipeline_run.identity.calendar_version,
        "feature_snapshot_id": source.snapshot.feature_snapshot_id,
        "forward_close_return": calculated.forward_close_return,
        "future_bar_count": len(calculated.future_bar_provenance),
        "future_bar_provenance": calculated.future_bar_provenance,
        "horizon": pipeline_run.identity.horizon,
        "latest_input_available_at": calculated.latest_input_available_at,
        "maximum_adverse_excursion_rate": calculated.maximum_adverse_excursion_rate,
        "maximum_favorable_excursion_rate": calculated.maximum_favorable_excursion_rate,
        "mic_code": scoring_item.mic_code,
        "observation_as_of": observation_as_of,
        "observation_mode": mode,
        "outcome_policy_code": policy_code,
        "outcome_policy_version": policy_version,
        "provider_code": pipeline_run.identity.provider_code,
        "reference_close": source.reference_close,
        "source_daily_feature_pipeline_item_id": (
            source.pipeline_item.daily_feature_pipeline_item_id
        ),
        "source_daily_feature_pipeline_run_id": pipeline_run.daily_feature_pipeline_run_id,
        "source_daily_feature_scoring_item_id": scoring_item.daily_feature_scoring_item_id,
        "source_daily_feature_scoring_run_id": scoring_run.daily_feature_scoring_run_id,
        "source_session_date": source_session_date,
        "symbol": scoring_item.symbol,
        "terminal_close": calculated.terminal_close,
        "terminal_session_date": calculated.terminal_session_date,
    }
    digest = outcome_content_digest(outcome_content_payload(common))
    return DailyFeatureOutcome(
        daily_feature_outcome_id=outcome_id,
        outcome_key=daily_feature_outcome_key(outcome_identity),
        content_digest=digest,
        path_revision_digest=path_digest,
        source_daily_feature_scoring_run_id=(scoring_run.daily_feature_scoring_run_id),
        source_daily_feature_scoring_item_id=(scoring_item.daily_feature_scoring_item_id),
        source_daily_feature_pipeline_run_id=(pipeline_run.daily_feature_pipeline_run_id),
        source_daily_feature_pipeline_item_id=(source.pipeline_item.daily_feature_pipeline_item_id),
        feature_snapshot_id=source.snapshot.feature_snapshot_id,
        symbol=scoring_item.symbol,
        mic_code=scoring_item.mic_code,
        provider_code=pipeline_run.identity.provider_code,
        calendar_code=pipeline_run.identity.calendar_code,
        calendar_version=pipeline_run.identity.calendar_version,
        source_session_date=source_session_date,
        terminal_session_date=calculated.terminal_session_date,
        horizon=pipeline_run.identity.horizon,
        outcome_policy_code=policy_code,
        outcome_policy_version=policy_version,
        observation_as_of=observation_as_of,
        reference_close=source.reference_close,
        terminal_close=calculated.terminal_close,
        forward_close_return=calculated.forward_close_return,
        maximum_favorable_excursion_rate=(calculated.maximum_favorable_excursion_rate),
        maximum_adverse_excursion_rate=(calculated.maximum_adverse_excursion_rate),
        future_bar_count=len(calculated.future_bar_provenance),
        future_bar_provenance=calculated.future_bar_provenance,
        latest_input_available_at=calculated.latest_input_available_at,
        observation_mode=mode,
        generated_at=generated_at,
        recorded_at=generated_at,
    )


def _matching_chain(
    scoring_item: DailyFeatureScoringItem,
    source_item: DailyFeaturePipelineItem,
    snapshot: FeatureSnapshot,
) -> bool:
    expected_outcome = {
        DailyFeatureScoringItemOutcome.SCORED_READY: DailyFeaturePipelineItemOutcome.READY,
        DailyFeatureScoringItemOutcome.SCORED_DEGRADED: DailyFeaturePipelineItemOutcome.DEGRADED,
    }.get(scoring_item.outcome)
    expected_quality = {
        DailyFeatureScoringItemOutcome.SCORED_READY: FeatureQualityStatus.READY,
        DailyFeatureScoringItemOutcome.SCORED_DEGRADED: FeatureQualityStatus.DEGRADED,
    }.get(scoring_item.outcome)
    return (
        expected_outcome is source_item.outcome
        and expected_quality is source_item.feature_quality_status
        and source_item.feature_snapshot_id == scoring_item.feature_snapshot_id
        and source_item.symbol == scoring_item.symbol
        and source_item.mic_code == scoring_item.mic_code
        and source_item.feature_quality_status == scoring_item.source_quality_status
        and source_item.completed_session_date is not None
        and snapshot.feature_snapshot_id == scoring_item.feature_snapshot_id
    )
