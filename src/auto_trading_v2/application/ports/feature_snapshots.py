"""Insert-only FeatureSnapshot repository boundary."""

from typing import Protocol

from auto_trading_v2.application.contracts.feature_snapshots import NewFeatureSnapshot
from auto_trading_v2.domain.feature_snapshots import FeatureSnapshot
from auto_trading_v2.domain.primitives import FeatureSnapshotID


class FeatureSnapshotRepository(Protocol):
    def add(self, snapshot: NewFeatureSnapshot) -> FeatureSnapshot: ...

    def get_by_id(self, feature_snapshot_id: FeatureSnapshotID) -> FeatureSnapshot | None: ...

    def get_by_snapshot_key(self, snapshot_key: str) -> FeatureSnapshot | None: ...
