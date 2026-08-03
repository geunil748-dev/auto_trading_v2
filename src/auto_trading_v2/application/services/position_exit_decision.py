"""Deterministic version-pinned EXIT_LONG decision orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.position_exit_decisions import (
    PositionExitDecisionOutcome,
    PositionExitDecisionResult,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewPositionStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    PersistenceError,
    PersistenceMappingError,
)
from auto_trading_v2.application.ports.id_factory import DecisionIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.position_exit_errors import (
    PositionExitPersistenceError,
    PositionExitSourceError,
)
from auto_trading_v2.application.services.position_exit_source import (
    PositionExitSource,
    load_position_exit_source,
)
from auto_trading_v2.domain.primitives import MarketSnapshotID, PositionID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.strategy_decisions import (
    PositionExitEvaluation,
    evaluate_position_exit,
    position_strategy_decision_key,
)
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class PositionExitDecisionService:
    """Create or return one canonical decision for a position and snapshot."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    decision_id_factory: DecisionIDFactory

    def decide(
        self,
        position_id: PositionID,
        market_snapshot_id: MarketSnapshotID,
    ) -> PositionExitDecisionResult:
        """Evaluate canonical sources while reading the Clock exactly once."""

        now = normalize_utc(self.clock.now_utc())
        try:
            return self._decide_once(position_id, market_snapshot_id, now)
        except DuplicateRecordError as exc:
            return self._resolve_duplicate(position_id, market_snapshot_id, now, exc)
        except PersistenceMappingError as exc:
            raise PositionExitSourceError(
                position_id,
                market_snapshot_id,
                f"invalid_{exc.entity}",
            ) from None
        except PersistenceError as exc:
            raise PositionExitPersistenceError(
                position_id,
                exc.constraint or exc.reason,
            ) from None

    def _decide_once(
        self,
        position_id: PositionID,
        market_snapshot_id: MarketSnapshotID,
        now: datetime,
    ) -> PositionExitDecisionResult:
        with self.unit_of_work_factory() as unit_of_work:
            source = load_position_exit_source(
                unit_of_work,
                position_id,
                market_snapshot_id,
                now,
            )
            existing = unit_of_work.strategy_decisions.get_by_position_snapshot_strategy(
                position_id=position_id,
                market_snapshot_id=market_snapshot_id,
                strategy_id=source.entry_decision.strategy_id,
                strategy_version=source.entry_decision.strategy_version,
            )
            if existing is not None:
                return _result(existing, PositionExitDecisionOutcome.ALREADY_DECIDED)

            evaluation = _evaluate(source)
            decision = NewPositionStrategyDecision(
                decision_id=self.decision_id_factory.new(),
                decision_key=position_strategy_decision_key(
                    position_id,
                    market_snapshot_id,
                    source.entry_decision.strategy_id,
                    source.entry_decision.strategy_version,
                ),
                position_id=position_id,
                position_version=source.position.version,
                market_snapshot_id=market_snapshot_id,
                strategy_id=source.entry_decision.strategy_id,
                strategy_version=source.entry_decision.strategy_version,
                action=evaluation.action,
                reason_codes=evaluation.reason_codes,
                decided_at=now,
            )
            stored = unit_of_work.strategy_decisions.add_position(decision)
            unit_of_work.commit()
            return _result(stored, PositionExitDecisionOutcome.CREATED, evaluation)

    def _resolve_duplicate(
        self,
        position_id: PositionID,
        market_snapshot_id: MarketSnapshotID,
        now: datetime,
        error: DuplicateRecordError,
    ) -> PositionExitDecisionResult:
        try:
            with self.unit_of_work_factory() as unit_of_work:
                source = load_position_exit_source(
                    unit_of_work,
                    position_id,
                    market_snapshot_id,
                    now,
                )
                existing = unit_of_work.strategy_decisions.get_by_position_snapshot_strategy(
                    position_id=position_id,
                    market_snapshot_id=market_snapshot_id,
                    strategy_id=source.entry_decision.strategy_id,
                    strategy_version=source.entry_decision.strategy_version,
                )
        except PersistenceMappingError as exc:
            raise PositionExitSourceError(
                position_id,
                market_snapshot_id,
                f"invalid_{exc.entity}",
            ) from None
        except PersistenceError as exc:
            raise PositionExitPersistenceError(
                position_id,
                exc.constraint or exc.reason,
            ) from None
        if existing is not None:
            return _result(existing, PositionExitDecisionOutcome.ALREADY_DECIDED)
        raise PositionExitPersistenceError(
            position_id,
            error.constraint or error.reason,
        ) from None


def _evaluate(source: PositionExitSource) -> PositionExitEvaluation:
    return evaluate_position_exit(
        average_cost_price=source.event.average_cost_after,
        current_price=source.snapshot.last_price,
        opened_at=source.position.opened_at,
        snapshot_observed_at=source.snapshot.observed_at,
        policy=source.policy,
    )


def _result(
    decision: StoredPositionStrategyDecision,
    outcome: PositionExitDecisionOutcome,
    evaluation: PositionExitEvaluation | None = None,
) -> PositionExitDecisionResult:
    return PositionExitDecisionResult(
        outcome=outcome,
        decision=decision,
        return_rate=None if evaluation is None else evaluation.return_rate,
        holding_duration=None if evaluation is None else evaluation.holding_duration,
    )
