"""Immutable P4B.2A label records."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import OutcomeObservationMode
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.outcome_labels.errors import OutcomeLabelValidationError
from auto_trading_v2.domain.outcome_labels.identity import (
    DailyFeatureOutcomeLabelIdentity,
    outcome_label_key,
)
from auto_trading_v2.domain.outcome_labels.outcomes import PositiveForwardCloseLabel
from auto_trading_v2.domain.outcome_labels.policies import (
    OutcomeLabelPolicyCode,
    OutcomeLabelPolicyVersion,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_LABEL_KEY = re.compile(r"^daily-feature-outcome-label:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeLabel:
    daily_feature_outcome_label_id: DailyFeatureOutcomeLabelID
    label_key: str
    content_digest: str
    source_daily_feature_outcome_id: DailyFeatureOutcomeID
    source_daily_feature_scoring_run_id: DailyFeatureScoringRunID
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    source_daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    source_daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    feature_snapshot_id: FeatureSnapshotID
    symbol: Symbol
    mic_code: str
    horizon: TradingDayHorizon
    source_session_date: SessionDate
    terminal_session_date: SessionDate
    observation_mode: OutcomeObservationMode
    source_path_revision_digest: str
    label_policy_code: OutcomeLabelPolicyCode
    label_policy_version: OutcomeLabelPolicyVersion
    label_value: PositiveForwardCloseLabel
    source_latest_input_available_at: datetime = field(repr=False)
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        self._validate_types()
        identity = DailyFeatureOutcomeLabelIdentity(
            self.source_daily_feature_outcome_id,
            self.label_policy_code,
            self.label_policy_version,
        )
        if not _LABEL_KEY.fullmatch(self.label_key) or self.label_key != outcome_label_key(
            identity
        ):
            _invalid("LABEL_KEY_INVALID")
        if not _DIGEST.fullmatch(self.content_digest):
            _invalid("LABEL_CONTENT_DIGEST_INVALID")
        if not _DIGEST.fullmatch(self.source_path_revision_digest):
            _invalid("LABEL_SOURCE_PATH_DIGEST_INVALID")
        latest = _timestamp(self.source_latest_input_available_at, "LABEL_SOURCE_AVAILABLE_INVALID")
        generated = _timestamp(self.generated_at, "LABEL_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "LABEL_RECORDED_AT_INVALID")
        if not latest <= generated <= recorded:
            _invalid("LABEL_TIME_ORDER_INVALID")
        object.__setattr__(self, "source_latest_input_available_at", latest)
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    def _validate_types(self) -> None:
        expected = (
            (self.daily_feature_outcome_label_id, DailyFeatureOutcomeLabelID),
            (self.source_daily_feature_outcome_id, DailyFeatureOutcomeID),
            (self.source_daily_feature_scoring_run_id, DailyFeatureScoringRunID),
            (self.source_daily_feature_scoring_item_id, DailyFeatureScoringItemID),
            (self.source_daily_feature_pipeline_run_id, DailyFeaturePipelineRunID),
            (self.source_daily_feature_pipeline_item_id, DailyFeaturePipelineItemID),
            (self.feature_snapshot_id, FeatureSnapshotID),
            (self.symbol, Symbol),
            (self.horizon, TradingDayHorizon),
            (self.source_session_date, SessionDate),
            (self.terminal_session_date, SessionDate),
            (self.observation_mode, OutcomeObservationMode),
            (self.label_policy_code, OutcomeLabelPolicyCode),
            (self.label_policy_version, OutcomeLabelPolicyVersion),
            (self.label_value, PositiveForwardCloseLabel),
        )
        if any(not isinstance(value, kind) for value, kind in expected):
            _invalid("LABEL_TYPE_INVALID")
        if (
            self.mic_code not in _MICS
            or self.source_session_date.value >= self.terminal_session_date.value
        ):
            _invalid("LABEL_SOURCE_CONTRACT_INVALID")


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        raise OutcomeLabelValidationError(category) from None


def _invalid(category: str) -> None:
    raise OutcomeLabelValidationError(category)
