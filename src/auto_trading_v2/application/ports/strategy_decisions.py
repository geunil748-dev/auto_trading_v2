"""Candidate and position strategy-decision repository boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    NewPositionStrategyDecision,
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    MarketSnapshotID,
    PositionID,
    StrategyID,
)


class StrategyDecisionRepository(Protocol):
    def add(
        self,
        decision: NewCandidateStrategyDecision,
    ) -> StoredCandidateStrategyDecision: ...

    def get(self, decision_id: DecisionID) -> StoredCandidateStrategyDecision | None: ...

    def get_by_candidate_strategy(
        self,
        *,
        candidate_id: CandidateID,
        strategy_id: StrategyID,
        strategy_version: str,
    ) -> StoredCandidateStrategyDecision | None: ...

    def list_by_candidate(
        self,
        candidate_id: CandidateID,
    ) -> Sequence[StoredCandidateStrategyDecision]: ...

    def add_position(
        self,
        decision: NewPositionStrategyDecision,
    ) -> StoredPositionStrategyDecision: ...

    def get_position(self, decision_id: DecisionID) -> StoredPositionStrategyDecision | None: ...

    def get_by_position_snapshot_strategy(
        self,
        *,
        position_id: PositionID,
        market_snapshot_id: MarketSnapshotID,
        strategy_id: StrategyID,
        strategy_version: str,
    ) -> StoredPositionStrategyDecision | None: ...
