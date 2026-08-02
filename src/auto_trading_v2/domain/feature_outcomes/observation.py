"""Immutable observation-run and run-item audit records."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)
from auto_trading_v2.domain.feature_outcomes.identity import (
    OutcomeObservationRunIdentity,
    daily_feature_outcome_observation_run_key,
)
from auto_trading_v2.domain.feature_outcomes.outcomes import (
    DailyFeatureOutcomeObservationRunItemOutcome,
    DailyFeatureOutcomeObservationRunStatus,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeObservationRunID,
    DailyFeatureOutcomeObservationRunItemID,
    DailyFeatureScoringItemID,
    SessionDate,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_RUN_KEY = re.compile(r"^daily-feature-outcome-run:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")
_OBSERVED = frozenset(
    {
        DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED,
        DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_ALREADY_EXISTS,
    }
)


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeObservationRunItem:
    daily_feature_outcome_observation_run_item_id: DailyFeatureOutcomeObservationRunItemID
    daily_feature_outcome_observation_run_id: DailyFeatureOutcomeObservationRunID
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    ordinal: int
    outcome: DailyFeatureOutcomeObservationRunItemOutcome
    daily_feature_outcome_id: DailyFeatureOutcomeID | None
    terminal_session_date: SessionDate | None
    safe_reason_code: str | None
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        expected = (
            (
                self.daily_feature_outcome_observation_run_item_id,
                DailyFeatureOutcomeObservationRunItemID,
            ),
            (
                self.daily_feature_outcome_observation_run_id,
                DailyFeatureOutcomeObservationRunID,
            ),
            (self.source_daily_feature_scoring_item_id, DailyFeatureScoringItemID),
            (self.outcome, DailyFeatureOutcomeObservationRunItemOutcome),
        )
        if any(not isinstance(value, kind) for value, kind in expected):
            _invalid("OBSERVATION_RUN_ITEM_TYPE_INVALID")
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int):
            _invalid("OBSERVATION_RUN_ITEM_ORDINAL_INVALID")
        if not 1 <= self.ordinal <= 100:
            _invalid("OBSERVATION_RUN_ITEM_ORDINAL_INVALID")
        observed = self.outcome in _OBSERVED
        if observed:
            if (
                not isinstance(self.daily_feature_outcome_id, DailyFeatureOutcomeID)
                or not isinstance(self.terminal_session_date, SessionDate)
                or self.safe_reason_code is not None
            ):
                _invalid("OBSERVATION_RUN_ITEM_OBSERVED_SHAPE_INVALID")
        elif (
            self.daily_feature_outcome_id is not None
            or self.safe_reason_code is None
            or not _REASON.fullmatch(self.safe_reason_code)
        ):
            _invalid("OBSERVATION_RUN_ITEM_UNOBSERVED_SHAPE_INVALID")
        generated = _timestamp(self.generated_at, "OBSERVATION_ITEM_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "OBSERVATION_ITEM_RECORDED_AT_INVALID")
        if generated > recorded:
            _invalid("OBSERVATION_RUN_ITEM_TIME_ORDER_INVALID")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    def digest_payload(self) -> dict[str, object]:
        return {
            "daily_feature_outcome_id": None
            if self.daily_feature_outcome_id is None
            else self.daily_feature_outcome_id.serialize(),
            "ordinal": self.ordinal,
            "outcome": self.outcome.value,
            "safe_reason_code": self.safe_reason_code,
            "source_daily_feature_scoring_item_id": (
                self.source_daily_feature_scoring_item_id.serialize()
            ),
            "terminal_session_date": None
            if self.terminal_session_date is None
            else self.terminal_session_date.serialize(),
        }


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeObservationRun:
    daily_feature_outcome_observation_run_id: DailyFeatureOutcomeObservationRunID
    observation_run_key: str
    content_digest: str
    identity: OutcomeObservationRunIdentity = field(repr=False)
    status: DailyFeatureOutcomeObservationRunStatus
    total_count: int
    outcome_created_count: int
    outcome_existing_count: int
    not_matured_count: int
    incomplete_count: int
    ineligible_count: int
    invalid_count: int
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(
            self.daily_feature_outcome_observation_run_id,
            DailyFeatureOutcomeObservationRunID,
        ):
            _invalid("OBSERVATION_RUN_ID_INVALID")
        if not _RUN_KEY.fullmatch(self.observation_run_key) or self.observation_run_key != (
            daily_feature_outcome_observation_run_key(self.identity)
        ):
            _invalid("OBSERVATION_RUN_KEY_INVALID")
        if not _DIGEST.fullmatch(self.content_digest):
            _invalid("OBSERVATION_RUN_DIGEST_INVALID")
        if not isinstance(self.status, DailyFeatureOutcomeObservationRunStatus):
            _invalid("OBSERVATION_RUN_STATUS_INVALID")
        counts = self.counts
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100
            for value in (self.total_count, *counts)
        ):
            _invalid("OBSERVATION_RUN_COUNT_INVALID")
        if self.total_count != sum(counts):
            _invalid("OBSERVATION_RUN_COUNT_SUM_INVALID")
        self._validate_status_shape()
        generated = _timestamp(self.generated_at, "OBSERVATION_RUN_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "OBSERVATION_RUN_RECORDED_AT_INVALID")
        if generated > recorded:
            _invalid("OBSERVATION_RUN_TIME_ORDER_INVALID")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    @property
    def counts(self) -> tuple[int, ...]:
        return (
            self.outcome_created_count,
            self.outcome_existing_count,
            self.not_matured_count,
            self.incomplete_count,
            self.ineligible_count,
            self.invalid_count,
        )

    def _validate_status_shape(self) -> None:
        pending = self.not_matured_count + self.incomplete_count
        if self.status is DailyFeatureOutcomeObservationRunStatus.COMPLETED:
            valid = pending == 0 and self.invalid_count == 0
        elif self.status is DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_PENDING:
            valid = pending > 0 and self.invalid_count == 0
        elif self.status is DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_GAPS:
            valid = self.invalid_count > 0
        elif self.status is DailyFeatureOutcomeObservationRunStatus.NO_ELIGIBLE_ITEMS:
            valid = self.total_count == self.ineligible_count
        else:
            valid = self.invalid_count > 0
        if not valid:
            _invalid("OBSERVATION_RUN_STATUS_SHAPE_INVALID")


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        raise OutcomeObservationValidationError(category) from None


def _invalid(category: str) -> None:
    raise OutcomeObservationValidationError(category)
