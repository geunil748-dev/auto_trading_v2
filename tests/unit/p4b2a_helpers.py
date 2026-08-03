from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetIdentity,
    fixed_dataset_policy_values,
)
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    SOURCE_PROVIDER_CODE,
    DailyFeatureOutcome,
    OutcomeObservationMode,
    fixed_outcome_policy_values,
)
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineItemOutcome
from auto_trading_v2.domain.feature_scoring import RelativeScore, fixed_policy_values
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.market_calendar import ExchangeCalendarCode, ExchangeCalendarVersion
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabel,
    DailyFeatureOutcomeLabelIdentity,
    fixed_label_policy_values,
    outcome_label_content_digest,
    outcome_label_key,
    positive_forward_close_label,
)
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeLabelID, Symbol
from tests.unit.application.feature_outcomes.test_service import _command, _service, _source
from tests.unit.domain.feature_outcomes.helpers import outcome_bar

DATASET_AS_OF = datetime(2026, 8, 5, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 6, tzinfo=UTC)
HORIZON_ONE = TradingDayHorizon(1)


def make_outcomes(
    values: tuple[tuple[str, str], ...],
    *,
    mode: OutcomeObservationMode = OutcomeObservationMode.PROSPECTIVE,
) -> tuple[DailyFeatureOutcome, ...]:
    scoring, pipeline, snapshots = _source(
        tuple((symbol, DailyFeaturePipelineItemOutcome.READY) for symbol, _ in values)
    )
    if mode is OutcomeObservationMode.RETROSPECTIVE_REPLAY:
        replay_time = datetime(2026, 8, 3, 20, tzinfo=UTC)
        scoring = replace(
            scoring,
            run=replace(scoring.run, generated_at=replay_time, recorded_at=replay_time),
        )
    bars = {
        symbol: (
            outcome_bar(
                1,
                close=close,
                high=str(max(Decimal(close), Decimal("100")) + Decimal("5")),
                low=str(min(Decimal(close), Decimal("100")) - Decimal("5")),
                symbol=Symbol(symbol),
                session_date=date(2026, 8, 3),
                available_at=datetime(2026, 8, 3, 22, tzinfo=UTC),
                source_version=f"{symbol.lower()}-v1",
            ),
        )
        for symbol, close in values
    }
    service, factory = _service(scoring, pipeline, snapshots, bars)
    result = service.observe(_command(scoring))
    assert result.result is not None
    outcomes = tuple(factory.outcomes.values.values())
    assert len(outcomes) == len(values)
    assert all(outcome.observation_mode is mode for outcome in outcomes)
    return outcomes


def make_label(
    outcome: DailyFeatureOutcome,
    *,
    identifier: int = 40_001,
    generated_at: datetime = DATASET_AS_OF,
) -> DailyFeatureOutcomeLabel:
    policy_code, policy_version = fixed_label_policy_values()
    label_value = positive_forward_close_label(outcome.forward_close_return)
    identity = DailyFeatureOutcomeLabelIdentity(
        outcome.daily_feature_outcome_id,
        policy_code,
        policy_version,
    )
    return DailyFeatureOutcomeLabel(
        daily_feature_outcome_label_id=DailyFeatureOutcomeLabelID(UUID(int=identifier)),
        label_key=outcome_label_key(identity),
        content_digest=outcome_label_content_digest(
            outcome,
            policy_code,
            policy_version,
            label_value,
        ),
        source_daily_feature_outcome_id=outcome.daily_feature_outcome_id,
        source_daily_feature_scoring_run_id=outcome.source_daily_feature_scoring_run_id,
        source_daily_feature_scoring_item_id=outcome.source_daily_feature_scoring_item_id,
        source_daily_feature_pipeline_run_id=outcome.source_daily_feature_pipeline_run_id,
        source_daily_feature_pipeline_item_id=outcome.source_daily_feature_pipeline_item_id,
        feature_snapshot_id=outcome.feature_snapshot_id,
        symbol=outcome.symbol,
        mic_code=outcome.mic_code,
        horizon=outcome.horizon,
        source_session_date=outcome.source_session_date,
        terminal_session_date=outcome.terminal_session_date,
        observation_mode=outcome.observation_mode,
        source_path_revision_digest=outcome.path_revision_digest,
        label_policy_code=policy_code,
        label_policy_version=policy_version,
        label_value=label_value,
        source_latest_input_available_at=outcome.latest_input_available_at,
        generated_at=generated_at,
        recorded_at=generated_at,
    )


def make_source(
    outcome: DailyFeatureOutcome,
    *,
    score: str = "75.5",
    rank: int = 1,
    quality: FeatureQualityStatus = FeatureQualityStatus.READY,
) -> CalibrationDatasetSourceRecord:
    scoring_time = datetime(2026, 8, 1, tzinfo=UTC)
    return CalibrationDatasetSourceRecord(
        source_daily_feature_scoring_run_id=outcome.source_daily_feature_scoring_run_id,
        source_daily_feature_scoring_item_id=outcome.source_daily_feature_scoring_item_id,
        source_daily_feature_pipeline_run_id=outcome.source_daily_feature_pipeline_run_id,
        source_daily_feature_pipeline_item_id=outcome.source_daily_feature_pipeline_item_id,
        feature_snapshot_id=outcome.feature_snapshot_id,
        source_daily_feature_outcome_id=outcome.daily_feature_outcome_id,
        source_outcome_key=outcome.outcome_key,
        source_outcome_content_digest=outcome.content_digest,
        source_path_revision_digest=outcome.path_revision_digest,
        symbol=outcome.symbol,
        mic_code=outcome.mic_code,
        horizon=outcome.horizon,
        source_session_date=outcome.source_session_date,
        terminal_session_date=outcome.terminal_session_date,
        source_scoring_generated_at=scoring_time,
        source_scoring_item_recorded_at=scoring_time,
        outcome_latest_input_available_at=outcome.latest_input_available_at,
        outcome_recorded_at=outcome.recorded_at,
        observation_mode=outcome.observation_mode,
        source_quality_status=quality,
        overall_relative_score=RelativeScore(Decimal(score)),
        rank=rank,
        forward_close_return=outcome.forward_close_return,
        provider_code=outcome.provider_code,
        calendar_code=outcome.calendar_code.value,
        calendar_version=outcome.calendar_version.value,
        outcome_policy_code=outcome.outcome_policy_code.value,
        outcome_policy_version=outcome.outcome_policy_version.value,
    )


def dataset_identity(
    *,
    as_of: datetime = DATASET_AS_OF,
    horizon: TradingDayHorizon = HORIZON_ONE,
) -> ProbabilityCalibrationDatasetIdentity:
    dataset_code, dataset_version = fixed_dataset_policy_values()
    label_code, label_version = fixed_label_policy_values()
    outcome_code, outcome_version = fixed_outcome_policy_values()
    scoring_code, scoring_version, ranking_code, ranking_version = fixed_policy_values()
    return ProbabilityCalibrationDatasetIdentity(
        dataset_code,
        dataset_version,
        label_code,
        label_version,
        outcome_code,
        outcome_version,
        scoring_code,
        scoring_version,
        ranking_code,
        ranking_version,
        SOURCE_PROVIDER_CODE,
        ExchangeCalendarCode(CALENDAR_CODE),
        ExchangeCalendarVersion(CALENDAR_VERSION),
        horizon,
        as_of,
    )
