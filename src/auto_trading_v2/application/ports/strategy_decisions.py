"""Candidate strategy-decision repository boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.domain.primitives import CandidateID, DecisionID, StrategyID


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
