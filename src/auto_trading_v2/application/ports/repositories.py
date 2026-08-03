"""Repository interfaces for the first persistence vertical slice."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from auto_trading_v2.application.contracts.persistence import (
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
    StoredCandidate,
    StoredFilterEvaluation,
    StoredMarketSnapshot,
)
from auto_trading_v2.domain.primitives import (
    CandidateID,
    FilterEvaluationID,
    MarketSnapshotID,
    RunID,
    Symbol,
)


class MarketSnapshotRepository(Protocol):
    def add(self, snapshot: NewMarketSnapshot) -> StoredMarketSnapshot: ...

    def get(self, market_snapshot_id: MarketSnapshotID) -> StoredMarketSnapshot | None: ...

    def get_by_observation(
        self, *, source: str, symbol: Symbol, observed_at: datetime
    ) -> StoredMarketSnapshot | None: ...


class CandidateRepository(Protocol):
    def add(self, candidate: NewCandidate) -> StoredCandidate: ...

    def get(self, candidate_id: CandidateID) -> StoredCandidate | None: ...

    def list_by_run(self, run_id: RunID) -> Sequence[StoredCandidate]: ...


class FilterEvaluationRepository(Protocol):
    def add(self, evaluation: NewFilterEvaluation) -> StoredFilterEvaluation: ...

    def get(self, filter_evaluation_id: FilterEvaluationID) -> StoredFilterEvaluation | None: ...

    def list_by_candidate(self, candidate_id: CandidateID) -> Sequence[StoredFilterEvaluation]: ...
