"""SQLAlchemy Core candidate and position strategy-decision repository."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.strategy_decision_mapping import (
    deserialize_reason_codes,
    map_position_strategy_decision,
    map_strategy_decision,
    serialize_reason_codes,
)
from auto_trading_v2.adapters.persistence.tables import strategy_decisions
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    NewPositionStrategyDecision,
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    MarketSnapshotID,
    PositionID,
    StrategyID,
)

__all__ = [
    "SqlAlchemyStrategyDecisionRepository",
    "deserialize_reason_codes",
    "map_position_strategy_decision",
    "map_strategy_decision",
    "serialize_reason_codes",
]


def _allow_operation() -> None:
    return None


class SqlAlchemyStrategyDecisionRepository:
    """Persist candidate and position decisions in the caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(
        self,
        decision: NewCandidateStrategyDecision,
    ) -> StoredCandidateStrategyDecision:
        self._ensure_active()
        try:
            values = {
                "decision_id": decision.decision_id.value,
                "decision_key": decision.decision_key,
                "candidate_id": decision.candidate_id.value,
                "position_id": None,
                "market_snapshot_id": None,
                "filter_evaluation_id": decision.filter_evaluation_id.value,
                "strategy_id": decision.strategy_id.value,
                "strategy_version": decision.strategy_version,
                "action": decision.action.value,
                "reason_codes": serialize_reason_codes(decision.reason_codes),
                "decided_at": decision.decided_at,
            }
            self._connection.execute(strategy_decisions.insert().values(**values))
            stored = self._select(decision.decision_id)
            if stored is None:
                raise PersistenceMappingError("strategy_decision", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="insert",
            ) from None

    def add_position(
        self,
        decision: NewPositionStrategyDecision,
    ) -> StoredPositionStrategyDecision:
        self._ensure_active()
        try:
            values = {
                "decision_id": decision.decision_id.value,
                "decision_key": decision.decision_key,
                "candidate_id": None,
                "position_id": decision.position_id.value,
                "market_snapshot_id": decision.market_snapshot_id.value,
                "filter_evaluation_id": None,
                "strategy_id": decision.strategy_id.value,
                "strategy_version": decision.strategy_version,
                "action": decision.action.value,
                "reason_codes": serialize_reason_codes(decision.reason_codes),
                "decided_at": decision.decided_at,
            }
            self._connection.execute(strategy_decisions.insert().values(**values))
            stored = self._select_position(decision.decision_id)
            if stored is None:
                raise PersistenceMappingError("strategy_decision", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="insert",
            ) from None

    def get(self, decision_id: DecisionID) -> StoredCandidateStrategyDecision | None:
        self._ensure_active()
        try:
            return self._select(decision_id)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="select",
            ) from None

    def get_by_candidate_strategy(
        self,
        *,
        candidate_id: CandidateID,
        strategy_id: StrategyID,
        strategy_version: str,
    ) -> StoredCandidateStrategyDecision | None:
        self._ensure_active()
        try:
            row = (
                self._connection.execute(
                    select(strategy_decisions).where(
                        strategy_decisions.c.candidate_id == candidate_id.value,
                        strategy_decisions.c.position_id.is_(None),
                        strategy_decisions.c.strategy_id == strategy_id.value,
                        strategy_decisions.c.strategy_version == strategy_version,
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else map_strategy_decision(row)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="select",
            ) from None

    def list_by_candidate(
        self,
        candidate_id: CandidateID,
    ) -> Sequence[StoredCandidateStrategyDecision]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(strategy_decisions)
                    .where(
                        strategy_decisions.c.candidate_id == candidate_id.value,
                        strategy_decisions.c.position_id.is_(None),
                    )
                    .order_by(
                        strategy_decisions.c.decided_at,
                        strategy_decisions.c.strategy_id,
                        strategy_decisions.c.decision_id,
                    )
                )
                .mappings()
                .all()
            )
            return tuple(map_strategy_decision(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="select",
            ) from None

    def get_position(self, decision_id: DecisionID) -> StoredPositionStrategyDecision | None:
        self._ensure_active()
        try:
            return self._select_position(decision_id)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="select",
            ) from None

    def get_by_position_snapshot_strategy(
        self,
        *,
        position_id: PositionID,
        market_snapshot_id: MarketSnapshotID,
        strategy_id: StrategyID,
        strategy_version: str,
    ) -> StoredPositionStrategyDecision | None:
        self._ensure_active()
        try:
            row = (
                self._connection.execute(
                    select(strategy_decisions).where(
                        strategy_decisions.c.candidate_id.is_(None),
                        strategy_decisions.c.position_id == position_id.value,
                        strategy_decisions.c.market_snapshot_id == market_snapshot_id.value,
                        strategy_decisions.c.strategy_id == strategy_id.value,
                        strategy_decisions.c.strategy_version == strategy_version,
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else map_position_strategy_decision(row)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="strategy_decision",
                operation="select",
            ) from None

    def _select(self, decision_id: DecisionID) -> StoredCandidateStrategyDecision | None:
        row = (
            self._connection.execute(
                select(strategy_decisions).where(
                    strategy_decisions.c.decision_id == decision_id.value,
                    strategy_decisions.c.candidate_id.is_not(None),
                    strategy_decisions.c.position_id.is_(None),
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_strategy_decision(row)

    def _select_position(
        self,
        decision_id: DecisionID,
    ) -> StoredPositionStrategyDecision | None:
        row = (
            self._connection.execute(
                select(strategy_decisions).where(
                    strategy_decisions.c.decision_id == decision_id.value,
                    strategy_decisions.c.candidate_id.is_(None),
                    strategy_decisions.c.position_id.is_not(None),
                    strategy_decisions.c.market_snapshot_id.is_not(None),
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_position_strategy_decision(row)
