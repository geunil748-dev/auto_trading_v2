"""Map canonical candidate and position strategy-decision rows."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    MarketSnapshotID,
    PositionID,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from auto_trading_v2.domain.strategy_decisions.reason_codes import normalize_reason_codes


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


def map_strategy_decision(row: Mapping[Any, Any]) -> StoredCandidateStrategyDecision:
    """Map one candidate-based row without exposing SQLAlchemy objects."""

    try:
        if row["candidate_id"] is None or row["filter_evaluation_id"] is None:
            raise TypeError
        if (
            row["position_id"] is not None
            or row["position_version"] is not None
            or row["market_snapshot_id"] is not None
        ):
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


def map_position_strategy_decision(
    row: Mapping[Any, Any],
) -> StoredPositionStrategyDecision:
    """Map one position-based row without accepting candidate source fields."""

    try:
        if row["candidate_id"] is not None or row["filter_evaluation_id"] is not None:
            raise TypeError
        if (
            row["position_id"] is None
            or row["position_version"] is None
            or row["market_snapshot_id"] is None
        ):
            raise TypeError
        return StoredPositionStrategyDecision(
            decision_id=DecisionID(_uuid(row["decision_id"])),
            decision_key=str(row["decision_key"]),
            position_id=PositionID(_uuid(row["position_id"])),
            position_version=_integer(row["position_version"]),
            market_snapshot_id=MarketSnapshotID(_uuid(row["market_snapshot_id"])),
            strategy_id=StrategyID(_uuid(row["strategy_id"])),
            strategy_version=str(row["strategy_version"]),
            action=StrategyAction(str(row["action"])),
            reason_codes=deserialize_reason_codes(row["reason_codes"]),
            decided_at=_datetime(row["decided_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("strategy_decision") from None


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value
