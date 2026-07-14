"""Atomic candidate strategy-decision orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

from auto_trading_v2.application.contracts.persistence import StoredFilterEvaluation
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.errors import (
    CandidateNotFoundError,
    DuplicateRecordError,
    InvalidFilterEvaluationError,
    RequiredFilterEvaluationMissingError,
    StrategyDecisionConflictError,
)
from auto_trading_v2.application.ports.id_factory import DecisionIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.primitives import CandidateID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.decision_keys import (
    candidate_strategy_decision_key,
)
from auto_trading_v2.domain.strategy_decisions.engine import (
    DeterministicStrategyDecisionEngine,
)
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError
from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyDefinition,
    StrategyJSONValue,
    StrategySignal,
)
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class StrategyDecisionBatchResult:
    """Stored candidate decisions in stable strategy catalog order."""

    candidate_id: CandidateID
    decisions: tuple[StoredCandidateStrategyDecision, ...]


@dataclass(frozen=True, slots=True)
class CandidateStrategyDecisionService:
    """Create exactly four candidate decisions from canonical evaluations."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    decision_id_factory: DecisionIDFactory
    engine: DeterministicStrategyDecisionEngine = field(
        default_factory=DeterministicStrategyDecisionEngine
    )
    strategies: tuple[StrategyDefinition, ...] = BUILT_IN_STRATEGIES

    def decide_all(self, candidate_id: CandidateID) -> StrategyDecisionBatchResult:
        """Validate all sources, then atomically store the full decision batch."""

        with self.unit_of_work_factory() as unit_of_work:
            candidate = unit_of_work.candidates.get(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(candidate_id)
            evaluations = unit_of_work.filter_evaluations.list_by_candidate(candidate_id)
            selected = self._select_signals(candidate_id, evaluations)

            decided_at = normalize_utc(self.clock.now_utc())
            stored: list[StoredCandidateStrategyDecision] = []
            for definition, evaluation, signal in selected:
                try:
                    result = self.engine.decide(signal, definition)
                except StrategyValidationError:
                    raise InvalidFilterEvaluationError(
                        candidate_id,
                        definition.source_filter_set_name,
                        definition.source_evaluation_version,
                        "invalid_contract",
                    ) from None
                decision = NewCandidateStrategyDecision(
                    decision_id=self.decision_id_factory.new(),
                    decision_key=candidate_strategy_decision_key(
                        candidate_id,
                        result.strategy_id,
                        result.strategy_version,
                    ),
                    candidate_id=candidate_id,
                    filter_evaluation_id=evaluation.filter_evaluation_id,
                    strategy_id=result.strategy_id,
                    strategy_version=result.strategy_version,
                    action=result.action,
                    reason_codes=result.reason_codes,
                    decided_at=decided_at,
                )
                try:
                    stored.append(unit_of_work.strategy_decisions.add(decision))
                except DuplicateRecordError:
                    unit_of_work.rollback()
                    raise StrategyDecisionConflictError(
                        candidate_id,
                        definition.name,
                        definition.strategy_version,
                    ) from None

            unit_of_work.commit()
        return StrategyDecisionBatchResult(candidate_id, tuple(stored))

    def _select_signals(
        self,
        candidate_id: CandidateID,
        evaluations: Sequence[StoredFilterEvaluation],
    ) -> tuple[tuple[StrategyDefinition, StoredFilterEvaluation, StrategySignal], ...]:
        selected: list[tuple[StrategyDefinition, StoredFilterEvaluation, StrategySignal]] = []
        for definition in self.strategies:
            matches = tuple(
                evaluation
                for evaluation in evaluations
                if evaluation.filter_set_id == definition.source_filter_set_id
                and evaluation.evaluation_version == definition.source_evaluation_version
            )
            if not matches:
                raise RequiredFilterEvaluationMissingError(
                    candidate_id,
                    definition.source_filter_set_name,
                    definition.source_evaluation_version,
                )
            if len(matches) != 1:
                raise InvalidFilterEvaluationError(
                    candidate_id,
                    definition.source_filter_set_name,
                    definition.source_evaluation_version,
                    "duplicate_source",
                )
            evaluation = matches[0]
            if evaluation.candidate_id != candidate_id:
                raise InvalidFilterEvaluationError(
                    candidate_id,
                    definition.source_filter_set_name,
                    definition.source_evaluation_version,
                    "candidate_mismatch",
                )
            if evaluation.score is None:
                raise InvalidFilterEvaluationError(
                    candidate_id,
                    definition.source_filter_set_name,
                    definition.source_evaluation_version,
                    "invalid_score",
                )
            try:
                details = cast(Mapping[str, StrategyJSONValue], evaluation.details)
                signal = StrategySignal(
                    filter_set_id=evaluation.filter_set_id,
                    evaluation_version=evaluation.evaluation_version,
                    passed=evaluation.passed,
                    score=evaluation.score,
                    details=details,
                )
            except StrategyValidationError:
                raise InvalidFilterEvaluationError(
                    candidate_id,
                    definition.source_filter_set_name,
                    definition.source_evaluation_version,
                    "invalid_contract",
                ) from None
            selected.append((definition, evaluation, signal))
        return tuple(selected)
