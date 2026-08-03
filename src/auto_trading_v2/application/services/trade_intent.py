"""Atomic TradeIntent generation from canonical strategy decisions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.application.errors import (
    CandidateNotFoundError,
    DuplicateRecordError,
    InvalidStrategyDecisionError,
    MarketSnapshotNotFoundError,
    RequiredStrategyDecisionMissingError,
    TradeIntentConflictError,
    TradeIntentRiskRejectedError,
)
from auto_trading_v2.application.ports.id_factory import TradeIntentIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.primitives import CandidateID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyAction,
    StrategyDefinition,
)
from auto_trading_v2.domain.trade_intents.idempotency import (
    trade_intent_idempotency_key,
)
from auto_trading_v2.domain.trade_intents.models import RiskOutcome
from auto_trading_v2.domain.trade_intents.risk import (
    INITIAL_FIXED_USD_NOTIONAL_POLICY,
    FixedNotionalRiskPolicy,
)
from auto_trading_v2.domain.trade_intents.sizing import plan_fixed_notional_quantity
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class TradeIntentBatchResult:
    """Stored intents in stable built-in strategy catalog order."""

    candidate_id: CandidateID
    trade_intents: tuple[StoredTradeIntent, ...]


@dataclass(frozen=True, slots=True)
class CandidateTradeIntentService:
    """Create BUY market intents for persisted ENTER_LONG decisions only."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    trade_intent_id_factory: TradeIntentIDFactory
    risk_policy: FixedNotionalRiskPolicy = INITIAL_FIXED_USD_NOTIONAL_POLICY
    strategies: tuple[StrategyDefinition, ...] = BUILT_IN_STRATEGIES

    def create_all(self, candidate_id: CandidateID) -> TradeIntentBatchResult:
        """Validate every source before atomically storing eligible intents."""

        with self.unit_of_work_factory() as unit_of_work:
            candidate = unit_of_work.candidates.get(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(candidate_id)
            snapshot = unit_of_work.market_snapshots.get(candidate.market_snapshot_id)
            if snapshot is None:
                raise MarketSnapshotNotFoundError(candidate.market_snapshot_id)
            decisions = unit_of_work.strategy_decisions.list_by_candidate(candidate_id)
            eligible = self._eligible_decisions(candidate_id, decisions)
            if not eligible:
                return TradeIntentBatchResult(candidate_id, ())

            sizing = plan_fixed_notional_quantity(snapshot.last_price, self.risk_policy)
            if sizing.outcome is RiskOutcome.REJECTED:
                raise TradeIntentRiskRejectedError(
                    candidate_id,
                    sizing.policy_name,
                    sizing.policy_version,
                    sizing.reason_codes[0],
                )
            if sizing.requested_quantity is None:
                raise TradeIntentRiskRejectedError(
                    candidate_id,
                    sizing.policy_name,
                    sizing.policy_version,
                    "invalid_result",
                )

            created_at = normalize_utc(self.clock.now_utc())
            stored: list[StoredTradeIntent] = []
            for definition, decision in eligible:
                new_intent = NewTradeIntent(
                    trade_intent_id=self.trade_intent_id_factory.new(),
                    decision_id=decision.decision_id,
                    idempotency_key=trade_intent_idempotency_key(
                        decision.decision_id,
                        self.risk_policy,
                    ),
                    symbol=snapshot.symbol,
                    currency=self.risk_policy.maximum_notional.currency,
                    side=self.risk_policy.side,
                    order_type=self.risk_policy.order_type,
                    requested_quantity=sizing.requested_quantity,
                    limit_price=None,
                    time_in_force=self.risk_policy.time_in_force,
                    created_at=created_at,
                )
                try:
                    stored.append(unit_of_work.trade_intents.add(new_intent))
                except DuplicateRecordError:
                    unit_of_work.rollback()
                    raise TradeIntentConflictError(
                        candidate_id,
                        definition.name,
                        definition.strategy_version,
                    ) from None
            unit_of_work.commit()
        return TradeIntentBatchResult(candidate_id, tuple(stored))

    def _eligible_decisions(
        self,
        candidate_id: CandidateID,
        decisions: Sequence[StoredCandidateStrategyDecision],
    ) -> tuple[tuple[StrategyDefinition, StoredCandidateStrategyDecision], ...]:
        eligible: list[tuple[StrategyDefinition, StoredCandidateStrategyDecision]] = []
        for definition in self.strategies:
            matches = tuple(
                decision
                for decision in decisions
                if decision.strategy_id == definition.strategy_id
                and decision.strategy_version == definition.strategy_version
            )
            if not matches:
                raise RequiredStrategyDecisionMissingError(
                    candidate_id,
                    definition.name,
                    definition.strategy_version,
                )
            if len(matches) != 1:
                raise InvalidStrategyDecisionError(
                    candidate_id,
                    definition.name,
                    definition.strategy_version,
                    "duplicate_source",
                )
            decision = matches[0]
            if decision.candidate_id != candidate_id:
                raise InvalidStrategyDecisionError(
                    candidate_id,
                    definition.name,
                    definition.strategy_version,
                    "candidate_mismatch",
                )
            self._validate_action(candidate_id, definition, decision.action)
            if decision.action is StrategyAction.ENTER_LONG:
                eligible.append((definition, decision))
        return tuple(eligible)

    @staticmethod
    def _validate_action(
        candidate_id: CandidateID,
        definition: StrategyDefinition,
        action: object,
    ) -> None:
        allowed = (
            (StrategyAction.OBSERVE,)
            if definition.observation_only
            else (StrategyAction.ENTER_LONG, StrategyAction.SKIP)
        )
        if action not in allowed:
            raise InvalidStrategyDecisionError(
                candidate_id,
                definition.name,
                definition.strategy_version,
                "unexpected_action",
            )
