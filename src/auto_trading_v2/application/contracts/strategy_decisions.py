"""Immutable candidate and position strategy-decision persistence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    MarketSnapshotID,
    PositionID,
    StrategyID,
)
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from auto_trading_v2.domain.strategy_decisions.reason_codes import normalize_reason_codes

DECISION_KEY_MAX_LENGTH = 160
_CANDIDATE_ACTIONS = frozenset(
    {StrategyAction.ENTER_LONG, StrategyAction.SKIP, StrategyAction.OBSERVE}
)
_POSITION_ACTIONS = frozenset({StrategyAction.EXIT_LONG, StrategyAction.SKIP})


def _require_instance(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{label} has an invalid type")


def _validate_code(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValidationError(f"{label} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class NewCandidateStrategyDecision:
    decision_id: DecisionID
    decision_key: str
    candidate_id: CandidateID
    filter_evaluation_id: FilterEvaluationID
    strategy_id: StrategyID
    strategy_version: str
    action: StrategyAction
    reason_codes: tuple[str, ...]
    decided_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.decision_id, DecisionID, "decision_id")
        _require_instance(self.candidate_id, CandidateID, "candidate_id")
        _require_instance(
            self.filter_evaluation_id,
            FilterEvaluationID,
            "filter_evaluation_id",
        )
        _require_instance(self.strategy_id, StrategyID, "strategy_id")
        _validate_action(self.action, _CANDIDATE_ACTIONS)
        if not isinstance(self.reason_codes, tuple):
            raise ValidationError("reason_codes must be a tuple")
        object.__setattr__(
            self,
            "decision_key",
            _validate_code(self.decision_key, "decision_key", DECISION_KEY_MAX_LENGTH),
        )
        if any(character.isspace() for character in self.decision_key):
            raise ValidationError("decision_key must not contain whitespace")
        object.__setattr__(
            self,
            "strategy_version",
            _validate_code(self.strategy_version, "strategy_version", 64),
        )
        object.__setattr__(
            self,
            "reason_codes",
            normalize_reason_codes(self.reason_codes),
        )
        object.__setattr__(self, "decided_at", normalize_utc(self.decided_at))


@dataclass(frozen=True, slots=True)
class StoredCandidateStrategyDecision(NewCandidateStrategyDecision):
    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredCandidateStrategyDecision, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


@dataclass(frozen=True, slots=True)
class NewPositionStrategyDecision:
    """Immutable persistence input for a position-based strategy decision."""

    decision_id: DecisionID
    decision_key: str
    position_id: PositionID
    market_snapshot_id: MarketSnapshotID
    strategy_id: StrategyID
    strategy_version: str
    action: StrategyAction
    reason_codes: tuple[str, ...]
    decided_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.decision_id, DecisionID, "decision_id")
        _require_instance(self.position_id, PositionID, "position_id")
        _require_instance(self.market_snapshot_id, MarketSnapshotID, "market_snapshot_id")
        _require_instance(self.strategy_id, StrategyID, "strategy_id")
        _validate_action(self.action, _POSITION_ACTIONS)
        if not isinstance(self.reason_codes, tuple):
            raise ValidationError("reason_codes must be a tuple")
        object.__setattr__(
            self,
            "decision_key",
            _validate_code(self.decision_key, "decision_key", DECISION_KEY_MAX_LENGTH),
        )
        if any(character.isspace() for character in self.decision_key):
            raise ValidationError("decision_key must not contain whitespace")
        object.__setattr__(
            self,
            "strategy_version",
            _validate_code(self.strategy_version, "strategy_version", 64),
        )
        object.__setattr__(self, "reason_codes", normalize_reason_codes(self.reason_codes))
        object.__setattr__(self, "decided_at", normalize_utc(self.decided_at))


@dataclass(frozen=True, slots=True)
class StoredPositionStrategyDecision(NewPositionStrategyDecision):
    """Stored position decision with the database recording timestamp."""

    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredPositionStrategyDecision, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


def _validate_action(action: object, allowed: frozenset[StrategyAction]) -> None:
    if not isinstance(action, StrategyAction):
        raise ValidationError("action has an invalid type")
    if action not in allowed:
        raise ValidationError("action is not allowed for this decision source")
