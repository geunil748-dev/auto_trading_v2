"""Immutable canonical P4B.1 forward-outcome revisions."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)
from auto_trading_v2.domain.feature_outcomes.identity import (
    DailyFeatureOutcomeIdentity,
    daily_feature_outcome_key,
    outcome_content_digest,
    path_revision_digest,
)
from auto_trading_v2.domain.feature_outcomes.outcomes import OutcomeObservationMode
from auto_trading_v2.domain.feature_outcomes.policies import (
    SOURCE_PROVIDER_CODE,
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
)
from auto_trading_v2.domain.feature_outcomes.provenance import (
    FutureBarProvenanceEntry,
    canonical_future_bar_provenance,
)
from auto_trading_v2.domain.feature_outcomes.values import (
    ExcursionRate,
    ForwardReturn,
    canonical_outcome_price,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc

_OUTCOME_KEY = re.compile(r"^daily-feature-outcome:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcome:
    daily_feature_outcome_id: DailyFeatureOutcomeID
    outcome_key: str
    content_digest: str
    path_revision_digest: str
    source_daily_feature_scoring_run_id: DailyFeatureScoringRunID
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    source_daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    source_daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    feature_snapshot_id: FeatureSnapshotID
    symbol: Symbol
    mic_code: str
    provider_code: str
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    source_session_date: SessionDate
    terminal_session_date: SessionDate
    horizon: TradingDayHorizon
    outcome_policy_code: OutcomeObservationPolicyCode
    outcome_policy_version: OutcomeObservationPolicyVersion
    observation_as_of: datetime
    reference_close: Decimal
    terminal_close: Decimal
    forward_close_return: ForwardReturn
    maximum_favorable_excursion_rate: ExcursionRate
    maximum_adverse_excursion_rate: ExcursionRate
    future_bar_count: int
    future_bar_provenance: tuple[FutureBarProvenanceEntry, ...] = field(repr=False)
    latest_input_available_at: datetime = field(repr=False)
    observation_mode: OutcomeObservationMode
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        provenance = canonical_future_bar_provenance(self.future_bar_provenance)
        object.__setattr__(self, "future_bar_provenance", provenance)
        object.__setattr__(
            self,
            "reference_close",
            canonical_outcome_price(self.reference_close, "REFERENCE_CLOSE_INVALID"),
        )
        object.__setattr__(
            self,
            "terminal_close",
            canonical_outcome_price(self.terminal_close, "TERMINAL_CLOSE_INVALID"),
        )
        observed = _timestamp(self.observation_as_of, "OBSERVATION_AS_OF_INVALID")
        latest = _timestamp(self.latest_input_available_at, "LATEST_INPUT_AVAILABLE_AT_INVALID")
        generated = _timestamp(self.generated_at, "OUTCOME_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "OUTCOME_RECORDED_AT_INVALID")
        if not latest <= observed <= generated <= recorded:
            _invalid("OUTCOME_TIME_ORDER_INVALID")
        for name, value in (
            ("observation_as_of", observed),
            ("latest_input_available_at", latest),
            ("generated_at", generated),
            ("recorded_at", recorded),
        ):
            object.__setattr__(self, name, value)
        self._validate_types()
        self._validate_identity_and_content()

    def _validate_types(self) -> None:
        expected = (
            (self.daily_feature_outcome_id, DailyFeatureOutcomeID),
            (self.source_daily_feature_scoring_run_id, DailyFeatureScoringRunID),
            (self.source_daily_feature_scoring_item_id, DailyFeatureScoringItemID),
            (self.source_daily_feature_pipeline_run_id, DailyFeaturePipelineRunID),
            (self.source_daily_feature_pipeline_item_id, DailyFeaturePipelineItemID),
            (self.feature_snapshot_id, FeatureSnapshotID),
            (self.symbol, Symbol),
            (self.source_session_date, SessionDate),
            (self.terminal_session_date, SessionDate),
            (self.horizon, TradingDayHorizon),
            (self.outcome_policy_code, OutcomeObservationPolicyCode),
            (self.outcome_policy_version, OutcomeObservationPolicyVersion),
            (self.observation_mode, OutcomeObservationMode),
        )
        if any(not isinstance(value, kind) for value, kind in expected):
            _invalid("OUTCOME_TYPE_INVALID")
        if self.mic_code not in _MICS or self.provider_code != SOURCE_PROVIDER_CODE:
            _invalid("OUTCOME_SOURCE_CONTRACT_INVALID")
        if self.source_session_date.value >= self.terminal_session_date.value:
            _invalid("OUTCOME_SESSION_ORDER_INVALID")
        if self.future_bar_count != self.horizon.value:
            _invalid("OUTCOME_FUTURE_BAR_COUNT_INVALID")
        if self.future_bar_count != len(self.future_bar_provenance):
            _invalid("OUTCOME_PROVENANCE_COUNT_INVALID")
        if self.future_bar_provenance[-1].session_date != self.terminal_session_date:
            _invalid("OUTCOME_TERMINAL_SESSION_INVALID")
        if max(entry.available_at for entry in self.future_bar_provenance) != (
            self.latest_input_available_at
        ):
            _invalid("OUTCOME_LATEST_INPUT_INVALID")
        if not (
            self.maximum_adverse_excursion_rate.value
            <= self.forward_close_return.value
            <= self.maximum_favorable_excursion_rate.value
        ):
            _invalid("OUTCOME_RATE_RELATION_INVALID")

    def _validate_identity_and_content(self) -> None:
        identity = DailyFeatureOutcomeIdentity(
            self.source_daily_feature_scoring_item_id,
            self.outcome_policy_code,
            self.outcome_policy_version,
            self.horizon,
            self.path_revision_digest,
        )
        if not _OUTCOME_KEY.fullmatch(self.outcome_key) or self.outcome_key != (
            daily_feature_outcome_key(identity)
        ):
            _invalid("OUTCOME_KEY_INVALID")
        if not _DIGEST.fullmatch(self.content_digest):
            _invalid("OUTCOME_CONTENT_DIGEST_INVALID")
        if self.path_revision_digest != path_revision_digest(self.future_bar_provenance):
            _invalid("PATH_REVISION_DIGEST_MISMATCH")
        if self.content_digest != daily_feature_outcome_content_digest(self):
            _invalid("OUTCOME_CONTENT_DIGEST_MISMATCH")

    def digest_payload(self) -> dict[str, object]:
        return {
            "calendar_code": self.calendar_code.value,
            "calendar_version": self.calendar_version.value,
            "feature_snapshot_id": self.feature_snapshot_id.serialize(),
            "forward_close_return": self.forward_close_return.serialize(),
            "future_bar_count": self.future_bar_count,
            "future_bar_provenance": [entry.as_json() for entry in self.future_bar_provenance],
            "horizon_trading_days": self.horizon.value,
            "latest_input_available_at": UtcTimestamp(self.latest_input_available_at).serialize(),
            "maximum_adverse_excursion_rate": (self.maximum_adverse_excursion_rate.serialize()),
            "maximum_favorable_excursion_rate": (self.maximum_favorable_excursion_rate.serialize()),
            "mic_code": self.mic_code,
            "observation_mode": self.observation_mode.value,
            "outcome_policy_code": self.outcome_policy_code.value,
            "outcome_policy_version": self.outcome_policy_version.value,
            "provider_code": self.provider_code,
            "reference_close": format(self.reference_close, ".18f"),
            "source_daily_feature_pipeline_item_id": (
                self.source_daily_feature_pipeline_item_id.serialize()
            ),
            "source_daily_feature_pipeline_run_id": (
                self.source_daily_feature_pipeline_run_id.serialize()
            ),
            "source_daily_feature_scoring_item_id": (
                self.source_daily_feature_scoring_item_id.serialize()
            ),
            "source_daily_feature_scoring_run_id": (
                self.source_daily_feature_scoring_run_id.serialize()
            ),
            "source_session_date": self.source_session_date.serialize(),
            "symbol": self.symbol.serialize(),
            "terminal_close": format(self.terminal_close, ".18f"),
            "terminal_session_date": self.terminal_session_date.serialize(),
        }


def daily_feature_outcome_content_digest(outcome: DailyFeatureOutcome) -> str:
    return outcome_content_digest(outcome.digest_payload())


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        raise OutcomeObservationValidationError(category) from None


def _invalid(category: str) -> None:
    raise OutcomeObservationValidationError(category)
