"""Result contract for deterministic position exit decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredPositionStrategyDecision,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    MarketSnapshotID,
    PositionID,
    Rate,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions import StrategyAction


class PositionExitDecisionOutcome(StrEnum):
    """Stable creation outcome for an idempotent position evaluation."""

    CREATED = "CREATED"
    ALREADY_DECIDED = "ALREADY_DECIDED"


@dataclass(frozen=True, slots=True)
class PositionExitDecisionResult:
    """Stored decision plus non-canonical diagnostics for a newly created row."""

    outcome: PositionExitDecisionOutcome
    decision: StoredPositionStrategyDecision
    return_rate: Rate | None = None
    holding_duration: timedelta | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, PositionExitDecisionOutcome):
            raise ValidationError("position exit outcome is invalid")
        if not isinstance(self.decision, StoredPositionStrategyDecision):
            raise ValidationError("position exit decision is invalid")
        if (self.return_rate is None) != (self.holding_duration is None):
            raise ValidationError("position exit diagnostics are incomplete")
        if self.return_rate is not None and not isinstance(self.return_rate, Rate):
            raise ValidationError("position exit return rate is invalid")
        if self.holding_duration is not None and (
            not isinstance(self.holding_duration, timedelta) or self.holding_duration < timedelta(0)
        ):
            raise ValidationError("position exit holding duration is invalid")

    @property
    def position_id(self) -> PositionID:
        return self.decision.position_id

    @property
    def position_version(self) -> int:
        return self.decision.position_version

    @property
    def market_snapshot_id(self) -> MarketSnapshotID:
        return self.decision.market_snapshot_id

    @property
    def strategy_id(self) -> StrategyID:
        return self.decision.strategy_id

    @property
    def strategy_version(self) -> str:
        return self.decision.strategy_version

    @property
    def action(self) -> StrategyAction:
        return self.decision.action

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return self.decision.reason_codes
