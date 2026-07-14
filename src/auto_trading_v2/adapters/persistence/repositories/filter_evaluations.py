"""SQLAlchemy Core filter-evaluation repository."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.mapping import (
    map_filter_evaluation,
    serialize_json_object,
)
from auto_trading_v2.adapters.persistence.tables import filter_evaluations
from auto_trading_v2.application.contracts.persistence import (
    NewFilterEvaluation,
    StoredFilterEvaluation,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import CandidateID, FilterEvaluationID


def _allow_operation() -> None:
    return None


class SqlAlchemyFilterEvaluationRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, evaluation: NewFilterEvaluation) -> StoredFilterEvaluation:
        self._ensure_active()
        values = {
            "filter_evaluation_id": evaluation.filter_evaluation_id.value,
            "candidate_id": evaluation.candidate_id.value,
            "filter_set_id": evaluation.filter_set_id.value,
            "evaluation_version": evaluation.evaluation_version,
            "passed": evaluation.passed,
            "score": evaluation.score,
            "details": serialize_json_object(evaluation.details),
            "evaluated_at": evaluation.evaluated_at,
        }
        try:
            self._connection.execute(filter_evaluations.insert().values(**values))
            stored = self._select(evaluation.filter_evaluation_id)
            if stored is None:
                raise PersistenceMappingError("filter_evaluation", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="filter_evaluation", operation="insert"
            ) from None

    def get(self, filter_evaluation_id: FilterEvaluationID) -> StoredFilterEvaluation | None:
        self._ensure_active()
        try:
            return self._select(filter_evaluation_id)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="filter_evaluation", operation="select"
            ) from None

    def list_by_candidate(self, candidate_id: CandidateID) -> Sequence[StoredFilterEvaluation]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(filter_evaluations)
                    .where(filter_evaluations.c.candidate_id == candidate_id.value)
                    .order_by(
                        filter_evaluations.c.evaluated_at,
                        filter_evaluations.c.filter_evaluation_id,
                    )
                )
                .mappings()
                .all()
            )
            return tuple(map_filter_evaluation(row) for row in rows)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="filter_evaluation", operation="select"
            ) from None

    def _select(self, filter_evaluation_id: FilterEvaluationID) -> StoredFilterEvaluation | None:
        row = (
            self._connection.execute(
                select(filter_evaluations).where(
                    filter_evaluations.c.filter_evaluation_id == filter_evaluation_id.value
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_filter_evaluation(row)
