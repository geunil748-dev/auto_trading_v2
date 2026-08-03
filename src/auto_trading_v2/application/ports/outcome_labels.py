"""Persistence port for immutable P4B.2A outcome labels."""

from typing import Protocol

from auto_trading_v2.application.contracts.outcome_labels import NewDailyFeatureOutcomeLabel
from auto_trading_v2.domain.outcome_labels import DailyFeatureOutcomeLabel
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeatureScoringItemID,
)


class DailyFeatureOutcomeLabelRepository(Protocol):
    def add(self, label: NewDailyFeatureOutcomeLabel) -> DailyFeatureOutcomeLabel: ...

    def get_by_id(
        self, label_id: DailyFeatureOutcomeLabelID
    ) -> DailyFeatureOutcomeLabel | None: ...

    def get_by_label_key(self, label_key: str) -> DailyFeatureOutcomeLabel | None: ...

    def get_by_source_outcome_and_policy(
        self,
        source_outcome_id: DailyFeatureOutcomeID,
        label_policy_code: str,
        label_policy_version: str,
    ) -> DailyFeatureOutcomeLabel | None: ...

    def list_by_source_scoring_item(
        self, source_item_id: DailyFeatureScoringItemID
    ) -> tuple[DailyFeatureOutcomeLabel, ...]: ...
