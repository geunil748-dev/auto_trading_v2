"""Aggregate persistence boundary for immutable P4A scoring runs."""

from typing import Protocol

from auto_trading_v2.application.contracts.feature_scoring import (
    NewDailyFeatureScoringRunWithItems,
)
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringItem,
    DailyFeatureScoringRun,
    DailyFeatureScoringRunWithItems,
)
from auto_trading_v2.domain.primitives import DailyFeatureScoringRunID


class DailyFeatureScoringRunRepository(Protocol):
    def add_run_with_items(
        self, aggregate: NewDailyFeatureScoringRunWithItems
    ) -> DailyFeatureScoringRunWithItems: ...

    def get_by_id(self, run_id: DailyFeatureScoringRunID) -> DailyFeatureScoringRun | None: ...

    def get_by_scoring_run_key(self, scoring_run_key: str) -> DailyFeatureScoringRun | None: ...

    def get_run_with_items(
        self, run_id: DailyFeatureScoringRunID
    ) -> DailyFeatureScoringRunWithItems | None: ...

    def list_items(
        self, run_id: DailyFeatureScoringRunID
    ) -> tuple[DailyFeatureScoringItem, ...]: ...
