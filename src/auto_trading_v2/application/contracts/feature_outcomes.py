"""Commands, results, and insert-only records for P4B.1 observations."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    DailyFeatureOutcome,
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunItem,
    DailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import DailyFeatureScoringRunID
from auto_trading_v2.domain.primitives.time import normalize_utc


@dataclass(frozen=True, slots=True)
class ObserveDailyFeatureScoringOutcomesCommand:
    daily_feature_scoring_run_id: DailyFeatureScoringRunID
    observation_as_of: datetime
    completion_grace: CompletionGracePeriod
    outcome_policy_code: str = OUTCOME_POLICY_CODE
    outcome_policy_version: str = OUTCOME_POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.daily_feature_scoring_run_id, DailyFeatureScoringRunID):
            raise ValueError("daily_feature_scoring_run_id is invalid")
        if not isinstance(self.completion_grace, CompletionGracePeriod):
            raise ValueError("completion_grace is invalid")
        seconds = self.completion_grace.value.total_seconds()
        if not seconds.is_integer():
            raise ValueError("completion_grace must use whole seconds")
        if (self.outcome_policy_code, self.outcome_policy_version) != (
            OUTCOME_POLICY_CODE,
            OUTCOME_POLICY_VERSION,
        ):
            raise ValueError("P4B.1 outcome policy is unsupported")
        try:
            normalized = normalize_utc(self.observation_as_of)
        except (TypeError, ValidationError):
            raise ValueError("observation_as_of must be timezone-aware") from None
        object.__setattr__(self, "observation_as_of", normalized)


@dataclass(frozen=True, slots=True)
class NewDailyFeatureOutcome:
    outcome: DailyFeatureOutcome

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, DailyFeatureOutcome):
            raise TypeError("outcome must be DailyFeatureOutcome")

    def stored(self, recorded_at: datetime) -> DailyFeatureOutcome:
        values = {
            name: getattr(self.outcome, name)
            for name in self.outcome.__dataclass_fields__
            if name != "recorded_at"
        }
        return DailyFeatureOutcome(**values, recorded_at=recorded_at)


@dataclass(frozen=True, slots=True)
class NewDailyFeatureOutcomeObservationRunWithItems:
    aggregate: DailyFeatureOutcomeObservationRunWithItems

    def __post_init__(self) -> None:
        if not isinstance(self.aggregate, DailyFeatureOutcomeObservationRunWithItems):
            raise TypeError("aggregate is invalid")

    def stored(self, recorded_at: datetime) -> DailyFeatureOutcomeObservationRunWithItems:
        run_values = {
            name: getattr(self.aggregate.run, name)
            for name in self.aggregate.run.__dataclass_fields__
            if name != "recorded_at"
        }
        run = DailyFeatureOutcomeObservationRun(**run_values, recorded_at=recorded_at)
        items = tuple(_stored_item(item, recorded_at) for item in self.aggregate.items)
        return DailyFeatureOutcomeObservationRunWithItems(run, items)


class DailyFeatureOutcomeObservationExecutionOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    SOURCE_SCORING_RUN_NOT_FOUND = "SOURCE_SCORING_RUN_NOT_FOUND"
    SOURCE_SCORING_RUN_NOT_ELIGIBLE = "SOURCE_SCORING_RUN_NOT_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeObservationExecutionResult:
    outcome: DailyFeatureOutcomeObservationExecutionOutcome
    result: DailyFeatureOutcomeObservationRunWithItems | None
    safe_reason_code: str | None = None

    def __post_init__(self) -> None:
        succeeded = self.outcome in {
            DailyFeatureOutcomeObservationExecutionOutcome.CREATED,
            DailyFeatureOutcomeObservationExecutionOutcome.ALREADY_EXISTS,
        }
        if succeeded != (self.result is not None):
            raise ValueError("outcome observation result shape is invalid")
        if succeeded == (self.safe_reason_code is not None):
            raise ValueError("outcome observation reason shape is invalid")


def _stored_item(
    item: DailyFeatureOutcomeObservationRunItem,
    recorded_at: datetime,
) -> DailyFeatureOutcomeObservationRunItem:
    values = {
        name: getattr(item, name) for name in item.__dataclass_fields__ if name != "recorded_at"
    }
    return DailyFeatureOutcomeObservationRunItem(**values, recorded_at=recorded_at)
