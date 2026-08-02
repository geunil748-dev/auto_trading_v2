"""Commands and insert-only records for P4B.2A outcome labels."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.outcome_labels import (
    LABEL_POLICY_CODE,
    LABEL_POLICY_VERSION,
    DailyFeatureOutcomeLabel,
)
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeID


@dataclass(frozen=True, slots=True)
class CreateDailyFeatureOutcomeLabelCommand:
    source_daily_feature_outcome_id: DailyFeatureOutcomeID
    label_policy_code: str = LABEL_POLICY_CODE
    label_policy_version: str = LABEL_POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source_daily_feature_outcome_id, DailyFeatureOutcomeID):
            raise ValueError("source_daily_feature_outcome_id is invalid")
        if (self.label_policy_code, self.label_policy_version) != (
            LABEL_POLICY_CODE,
            LABEL_POLICY_VERSION,
        ):
            raise ValueError("P4B.2A label policy is unsupported")


@dataclass(frozen=True, slots=True)
class NewDailyFeatureOutcomeLabel:
    label: DailyFeatureOutcomeLabel

    def __post_init__(self) -> None:
        if not isinstance(self.label, DailyFeatureOutcomeLabel):
            raise TypeError("label must be DailyFeatureOutcomeLabel")

    def stored(self, recorded_at: datetime) -> DailyFeatureOutcomeLabel:
        values = {
            name: getattr(self.label, name)
            for name in self.label.__dataclass_fields__
            if name != "recorded_at"
        }
        return DailyFeatureOutcomeLabel(**values, recorded_at=recorded_at)


class DailyFeatureOutcomeLabelCreationOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeLabelCreationResult:
    outcome: DailyFeatureOutcomeLabelCreationOutcome
    label: DailyFeatureOutcomeLabel
