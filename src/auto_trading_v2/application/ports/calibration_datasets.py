"""Persistence and source-selection ports for P4B.2A datasets."""

from datetime import datetime
from typing import Protocol

from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.calibration_datasets import (
    CalibrationDatasetPolicyCode,
    CalibrationDatasetPolicyVersion,
    ProbabilityCalibrationDataset,
    ProbabilityCalibrationDatasetItem,
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import ProbabilityCalibrationDatasetID


class ProbabilityCalibrationDatasetSourceReader(Protocol):
    def list_eligible_sources(
        self,
        horizon: TradingDayHorizon,
        dataset_as_of: datetime,
        dataset_policy_code: CalibrationDatasetPolicyCode,
        dataset_policy_version: CalibrationDatasetPolicyVersion,
    ) -> tuple[CalibrationDatasetSourceRecord, ...]: ...


class ProbabilityCalibrationDatasetRepository(Protocol):
    def add_dataset_with_items(
        self, aggregate: NewProbabilityCalibrationDatasetWithItems
    ) -> ProbabilityCalibrationDatasetWithItems: ...

    def get_by_id(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> ProbabilityCalibrationDataset | None: ...

    def get_by_dataset_key(self, dataset_key: str) -> ProbabilityCalibrationDataset | None: ...

    def get_dataset_with_items(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> ProbabilityCalibrationDatasetWithItems | None: ...

    def list_items(
        self, dataset_id: ProbabilityCalibrationDatasetID
    ) -> tuple[ProbabilityCalibrationDatasetItem, ...]: ...
