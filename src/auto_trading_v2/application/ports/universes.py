"""UniverseSnapshot persistence boundary."""

from typing import Protocol

from auto_trading_v2.application.contracts.universes import NewUniverseSnapshot
from auto_trading_v2.domain.primitives import UniverseSnapshotID
from auto_trading_v2.domain.universes import UniverseCode, UniverseSnapshot, UniverseVersion


class UniverseSnapshotRepository(Protocol):
    def add(self, snapshot: NewUniverseSnapshot) -> UniverseSnapshot: ...

    def get_by_id(self, universe_snapshot_id: UniverseSnapshotID) -> UniverseSnapshot | None: ...

    def get_by_universe_key(self, universe_key: str) -> UniverseSnapshot | None: ...

    def get_by_code_and_version(
        self,
        universe_code: UniverseCode,
        universe_version: UniverseVersion,
    ) -> UniverseSnapshot | None: ...
