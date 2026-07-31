"""Pipeline run aggregate persistence boundary."""

from typing import Protocol

from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItem,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunWithItems,
)
from auto_trading_v2.domain.primitives import DailyFeaturePipelineRunID


class DailyFeaturePipelineRunRepository(Protocol):
    def add_run_with_items(
        self,
        aggregate: NewDailyFeaturePipelineRunWithItems,
    ) -> DailyFeaturePipelineRunWithItems: ...

    def get_by_id(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> DailyFeaturePipelineRun | None: ...

    def get_by_run_key(self, run_key: str) -> DailyFeaturePipelineRun | None: ...

    def list_items(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> tuple[DailyFeaturePipelineItem, ...]: ...

    def get_run_with_items(
        self,
        run_id: DailyFeaturePipelineRunID,
    ) -> DailyFeaturePipelineRunWithItems | None: ...
