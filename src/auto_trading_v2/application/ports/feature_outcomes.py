"""Persistence ports for immutable P4B.1 outcomes and observation audits."""

from datetime import datetime
from typing import Protocol

from auto_trading_v2.application.contracts.feature_outcomes import (
    NewDailyFeatureOutcome,
    NewDailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcome,
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunItem,
    DailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeObservationRunID,
    DailyFeatureScoringItemID,
)


class DailyFeatureOutcomeRepository(Protocol):
    def add(self, outcome: NewDailyFeatureOutcome) -> DailyFeatureOutcome: ...

    def get_by_id(self, outcome_id: DailyFeatureOutcomeID) -> DailyFeatureOutcome | None: ...

    def get_by_outcome_key(self, outcome_key: str) -> DailyFeatureOutcome | None: ...

    def list_by_source_scoring_item(
        self, source_item_id: DailyFeatureScoringItemID
    ) -> tuple[DailyFeatureOutcome, ...]: ...

    def get_latest_available_by_source_scoring_item(
        self,
        source_item_id: DailyFeatureScoringItemID,
        as_of: datetime,
    ) -> DailyFeatureOutcome | None: ...


class DailyFeatureOutcomeObservationRunRepository(Protocol):
    def add_run_with_items(
        self, aggregate: NewDailyFeatureOutcomeObservationRunWithItems
    ) -> DailyFeatureOutcomeObservationRunWithItems: ...

    def get_by_id(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> DailyFeatureOutcomeObservationRun | None: ...

    def get_by_observation_run_key(
        self, observation_run_key: str
    ) -> DailyFeatureOutcomeObservationRun | None: ...

    def get_run_with_items(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> DailyFeatureOutcomeObservationRunWithItems | None: ...

    def list_items(
        self, run_id: DailyFeatureOutcomeObservationRunID
    ) -> tuple[DailyFeatureOutcomeObservationRunItem, ...]: ...
