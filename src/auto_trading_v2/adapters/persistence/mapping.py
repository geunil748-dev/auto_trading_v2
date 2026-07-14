"""Map canonical SQLAlchemy Core rows to application contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.persistence import (
    FrozenJSONList,
    JSONValue,
    StoredCandidate,
    StoredFilterEvaluation,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    FilterEvaluationID,
    FilterSetID,
    MarketSnapshotID,
    Price,
    RunID,
    SessionDate,
    Symbol,
)


def serialize_json_object(value: Mapping[str, JSONValue]) -> str:
    """Serialize a validated JSON object with deterministic Unicode output."""

    ready = _json_ready(value)
    if not isinstance(ready, dict):
        raise PersistenceMappingError("filter_evaluation", "serialize")
    return json.dumps(ready, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_ready(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, FrozenJSONList):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise PersistenceMappingError("filter_evaluation", "serialize")
        return {str(key): _json_ready(item) for key, item in value.items()}
    raise PersistenceMappingError("filter_evaluation", "serialize")


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def map_market_snapshot(row: Mapping[Any, Any]) -> StoredMarketSnapshot:
    try:
        session_date = row["session_date"]
        if type(session_date) is not date:
            raise TypeError
        previous_close = row["previous_close_price"]
        return StoredMarketSnapshot(
            market_snapshot_id=MarketSnapshotID(_uuid(row["market_snapshot_id"])),
            symbol=Symbol(str(row["symbol"])),
            session_date=SessionDate(session_date),
            observed_at=_datetime(row["observed_at"]),
            source=str(row["source"]),
            open_price=Price(_decimal(row["open_price"])),
            high_price=Price(_decimal(row["high_price"])),
            low_price=Price(_decimal(row["low_price"])),
            last_price=Price(_decimal(row["last_price"])),
            previous_high_price=Price(_decimal(row["previous_high_price"])),
            previous_low_price=Price(_decimal(row["previous_low_price"])),
            previous_close_price=(
                None if previous_close is None else Price(_decimal(previous_close))
            ),
            volume=None if row["volume"] is None else int(row["volume"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise PersistenceMappingError("market_snapshot") from None


def map_candidate(row: Mapping[Any, Any]) -> StoredCandidate:
    try:
        source_score = row["source_score"]
        return StoredCandidate(
            candidate_id=CandidateID(_uuid(row["candidate_id"])),
            run_id=RunID(_uuid(row["run_id"])),
            market_snapshot_id=MarketSnapshotID(_uuid(row["market_snapshot_id"])),
            candidate_source=str(row["candidate_source"]),
            rank=None if row["rank"] is None else int(row["rank"]),
            source_score=None if source_score is None else _decimal(source_score),
            selected_at=_datetime(row["selected_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise PersistenceMappingError("candidate") from None


def map_filter_evaluation(row: Mapping[Any, Any]) -> StoredFilterEvaluation:
    try:
        raw_details = row["details"]
        if not isinstance(raw_details, str):
            raise TypeError
        details = json.loads(raw_details)
        if not isinstance(details, dict):
            raise TypeError
        score = row["score"]
        return StoredFilterEvaluation(
            filter_evaluation_id=FilterEvaluationID(_uuid(row["filter_evaluation_id"])),
            candidate_id=CandidateID(_uuid(row["candidate_id"])),
            filter_set_id=FilterSetID(_uuid(row["filter_set_id"])),
            evaluation_version=str(row["evaluation_version"]),
            passed=bool(row["passed"]),
            score=None if score is None else _decimal(score),
            details=details,
            evaluated_at=_datetime(row["evaluated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, json.JSONDecodeError):
        raise PersistenceMappingError("filter_evaluation") from None
