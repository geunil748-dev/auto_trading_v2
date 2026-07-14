"""SQLAlchemy Core candidate strategy-decision repository."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import strategy_decisions
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from auto_trading_v2.domain.strategy_decisions.reason_codes import normalize_reason_codes


def _allow_operation() -> None:
    return None


def serialize_reason_codes(reason_codes: tuple[str, ...]) -> str:
    """Serialize a validated ordered code tuple as compact Unicode JSON."""

    try:
        normalized = normalize_reason_codes(reason_codes)
    except ValidationError:
        raise PersistenceMappingError("strategy_decision", "serialize") from None
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def deserialize_reason_codes(raw: object) -> tuple[str, ...]:
    """Deserialize a canonical JSON array without exposing rejected content."""

    try:
        if not isinstance(raw, str):
            raise TypeError
        decoded = json.loads(raw)
        if not isinstance(decoded, list):
            raise TypeError
        return normalize_reason_codes(decoded)
    except (TypeError, ValueError, json.JSONDecodeError, ValidationError):
        raise PersistenceMappingError("strategy_decision", "deserialize") from None


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def map_strategy_decision(row: Mapping[Any, Any]) -> StoredCandidateStrategyDecision:
    """Map one candidate-based row without exposing SQLAlchemy objects."""

    try:
        if row["candidate_id"] is None or row["filter_evaluation_id"] is None:
            raise TypeError
        if row["position_id"] is not None:
            raise TypeError
        return StoredCandidateStrategyDecision(
            decision_id=DecisionID(_uuid(row["decision_id"])),
            decision_key=str(row["decision_key"]),
            candidate_id=CandidateID(_uuid(row["candidate_id"])),
            filter_evaluation_id=FilterEvaluationID(_uuid(row["filter_evaluation_id"])),
            strategy_id=StrategyID(_uuid(row["strategy_id"])),
            strategy_version=str(row["strategy_version"]),
            action=StrategyAction(str(row["action"])),
            reason_codes=deserialize_reason_codes(row["reason_codes"]),
            decided_at=_datetime(row["decided_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("strategy_decision") from None


class SqlAlchemyStrategyDecisionRepository:
    """Persist candidate decisions within the caller-owned transaction."""

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
