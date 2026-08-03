"""Atomic multi-filter evaluation orchestration for one candidate."""

from __future__ import annotations

from dataclasses import dataclass, field

from auto_trading_v2.application.contracts.persistence import (
    NewFilterEvaluation,
    StoredFilterEvaluation,
)
from auto_trading_v2.application.errors import (
    CandidateNotFoundError,
    DuplicateRecordError,
    FilterEvaluationConflictError,
    MarketSnapshotNotFoundError,
)
from auto_trading_v2.application.ports.id_factory import FilterEvaluationIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.filtering.catalog import BUILT_IN_FILTER_SETS
from auto_trading_v2.domain.filtering.details import build_filter_evaluation_details
from auto_trading_v2.domain.filtering.engine import DeterministicFilterEngine
from auto_trading_v2.domain.filtering.models import (
    FilterInput,
    FilterJSONValue,
    FilterSetDefinition,
)
from auto_trading_v2.domain.primitives import CandidateID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class EvaluationBatchResult:
    """Stored evaluations in deterministic built-in filter-set order."""

    candidate_id: CandidateID
    evaluations: tuple[StoredFilterEvaluation, ...]


@dataclass(frozen=True, slots=True)
class CandidateFilterEvaluationService:
    """Evaluate and atomically store all built-in policies for one candidate."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    filter_evaluation_id_factory: FilterEvaluationIDFactory
    engine: DeterministicFilterEngine = field(default_factory=DeterministicFilterEngine)
    filter_sets: tuple[FilterSetDefinition, ...] = BUILT_IN_FILTER_SETS

    def evaluate_all(self, candidate_id: CandidateID) -> EvaluationBatchResult:
        """Store exactly four versioned evaluations in one Unit of Work."""

        with self.unit_of_work_factory() as unit_of_work:
            candidate = unit_of_work.candidates.get(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(candidate_id)
            snapshot = unit_of_work.market_snapshots.get(candidate.market_snapshot_id)
            if snapshot is None:
                raise MarketSnapshotNotFoundError(candidate.market_snapshot_id)

            filter_input = FilterInput(
                symbol=snapshot.symbol,
                open_price=snapshot.open_price,
                last_price=snapshot.last_price,
                previous_high_price=snapshot.previous_high_price,
                previous_low_price=snapshot.previous_low_price,
                previous_close_price=snapshot.previous_close_price,
                volume=snapshot.volume,
            )
            evaluated_at = normalize_utc(self.clock.now_utc())
            stored: list[StoredFilterEvaluation] = []
            for definition in self.filter_sets:
                result = self.engine.evaluate(filter_input, definition)
                details: dict[str, FilterJSONValue] = build_filter_evaluation_details(result)
                evaluation = NewFilterEvaluation(
                    filter_evaluation_id=self.filter_evaluation_id_factory.new(),
                    candidate_id=candidate.candidate_id,
                    filter_set_id=result.filter_set_id,
                    evaluation_version=result.evaluation_version,
                    passed=result.passed,
                    score=result.score,
                    details=details,
                    evaluated_at=evaluated_at,
                )
                try:
                    stored.append(unit_of_work.filter_evaluations.add(evaluation))
                except DuplicateRecordError:
                    unit_of_work.rollback()
                    raise FilterEvaluationConflictError(definition.name) from None

            unit_of_work.commit()
        return EvaluationBatchResult(candidate_id, tuple(stored))
