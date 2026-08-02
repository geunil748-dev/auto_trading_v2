"""Internal immutable records shared by P4B.1 application services."""

from dataclasses import dataclass

from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcome,
    DailyFeatureOutcomeObservationRunItemOutcome,
)
from auto_trading_v2.domain.feature_scoring import DailyFeatureScoringItem
from auto_trading_v2.domain.primitives import SessionDate


@dataclass(frozen=True, slots=True)
class PreparedOutcomeItem:
    source_item: DailyFeatureScoringItem
    outcome: DailyFeatureOutcomeObservationRunItemOutcome
    candidate: DailyFeatureOutcome | None = None
    terminal_session_date: SessionDate | None = None
