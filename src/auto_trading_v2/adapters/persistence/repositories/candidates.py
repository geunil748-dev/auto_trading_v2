"""SQLAlchemy Core candidate repository."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.mapping import map_candidate
from auto_trading_v2.adapters.persistence.tables import candidates
from auto_trading_v2.application.contracts.persistence import NewCandidate, StoredCandidate
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import CandidateID, RunID


def _allow_operation() -> None:
    return None


class SqlAlchemyCandidateRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, candidate: NewCandidate) -> StoredCandidate:
        self._ensure_active()
        values = {
            "candidate_id": candidate.candidate_id.value,
            "run_id": candidate.run_id.value,
            "market_snapshot_id": candidate.market_snapshot_id.value,
            "candidate_source": candidate.candidate_source,
            "rank": candidate.rank,
            "source_score": candidate.source_score,
            "selected_at": candidate.selected_at,
        }
        try:
            self._connection.execute(candidates.insert().values(**values))
            stored = self._select(candidate.candidate_id)
            if stored is None:
                raise PersistenceMappingError("candidate", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(exc, entity="candidate", operation="insert") from None

    def get(self, candidate_id: CandidateID) -> StoredCandidate | None:
        self._ensure_active()
        try:
            return self._select(candidate_id)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(exc, entity="candidate", operation="select") from None

    def list_by_run(self, run_id: RunID) -> Sequence[StoredCandidate]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(candidates)
                    .where(candidates.c.run_id == run_id.value)
                    .order_by(candidates.c.selected_at, candidates.c.candidate_id)
                )
                .mappings()
                .all()
            )
            return tuple(map_candidate(row) for row in rows)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(exc, entity="candidate", operation="select") from None

    def _select(self, candidate_id: CandidateID) -> StoredCandidate | None:
        row = (
            self._connection.execute(
                select(candidates).where(candidates.c.candidate_id == candidate_id.value)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_candidate(row)
