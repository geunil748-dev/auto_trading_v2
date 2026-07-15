"""Atomic execution of exactly one deterministic fill for one PaperOrder."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from auto_trading_v2.application.contracts.paper_fills import (
    NewPaperFill,
    PaperFillExecutionResult,
    PaperOrderFillTransition,
)
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    InvalidPaperFillHistoryError,
    OptimisticConcurrencyError,
    PaperFillConflictError,
    PaperFillSourceError,
    PaperOrderConcurrencyError,
    PaperOrderNotFillableError,
    PaperOrderNotFoundError,
    PersistenceNotFoundError,
    UnsupportedPaperOrderBrokerError,
)
from auto_trading_v2.application.ports.id_factory import FillIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.paper_fills import (
    INTERNAL_PAPER_SPLIT_FILL_POLICY,
    InternalPaperSplitFillPolicy,
    PaperFillHistoryValidationError,
    paper_fill_execution_key,
    validate_fill_history,
)
from auto_trading_v2.domain.paper_orders import INTERNAL_PAPER_BROKER_CODE, PaperOrderStatus
from auto_trading_v2.domain.primitives import Currency, Money, OrderID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class PaperFillExecutionService:
    """Create one canonical fill and atomically advance the current order."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    fill_id_factory: FillIDFactory
    fill_policy: InternalPaperSplitFillPolicy = INTERNAL_PAPER_SPLIT_FILL_POLICY

    def execute_next(self, order_id: OrderID) -> PaperFillExecutionResult:
        with self.unit_of_work_factory() as unit_of_work:
            order = unit_of_work.paper_orders.get(order_id)
            if order is None:
                raise PaperOrderNotFoundError(order_id)
            self._validate_fillable_order(order)
            intent = unit_of_work.trade_intents.get(order.trade_intent_id)
            if intent is None:
                raise PaperFillSourceError(order_id, "trade_intent_missing")
            decision = unit_of_work.strategy_decisions.get(intent.decision_id)
            if decision is None:
                raise PaperFillSourceError(order_id, "strategy_decision_missing")
            candidate = unit_of_work.candidates.get(decision.candidate_id)
            if candidate is None:
                raise PaperFillSourceError(order_id, "candidate_missing")
            snapshot = unit_of_work.market_snapshots.get(candidate.market_snapshot_id)
            if snapshot is None:
                raise PaperFillSourceError(order_id, "market_snapshot_missing")
            if intent.symbol != snapshot.symbol:
                raise PaperFillSourceError(order_id, "symbol_mismatch")
            self._validate_accepted_intent(order_id, intent)

            plan = self.fill_policy.plan(intent.requested_quantity)
            fills = tuple(unit_of_work.paper_fills.list_by_order(order_id))
            if order.accepted_at is None:
                raise InvalidPaperFillHistoryError(order_id, "acceptance_missing")
            try:
                cumulative = validate_fill_history(
                    order_id=order_id,
                    order_status=order.status,
                    order_accepted_at=order.accepted_at,
                    plan=plan,
                    reference_price=snapshot.last_price,
                    fee_currency=intent.currency,
                    fills=fills,
                )
            except PaperFillHistoryValidationError as exc:
                raise InvalidPaperFillHistoryError(order_id, exc.reason) from None
            if len(fills) >= len(plan.quantities):
                raise InvalidPaperFillHistoryError(order_id, "fill_plan_exhausted")

            executed_at = normalize_utc(self.clock.now_utc())
            if executed_at < order.updated_at:
                raise PaperFillSourceError(order_id, "clock_precedes_order")
            sequence = len(fills) + 1
            quantity = plan.quantities[len(fills)]
            new_fill = NewPaperFill(
                fill_id=self.fill_id_factory.new(),
                order_id=order_id,
                execution_key=paper_fill_execution_key(order_id, sequence),
                fill_sequence=sequence,
                quantity=quantity,
                price=snapshot.last_price,
                fee=Money(Decimal("0"), intent.currency),
                executed_at=executed_at,
            )
            filled_quantity = cumulative.value + quantity.value
            final = filled_quantity == intent.requested_quantity.value
            transition = PaperOrderFillTransition(
                order_id=order_id,
                expected_status=order.status,
                expected_version=order.version,
                new_status=(
                    PaperOrderStatus.FILLED if final else PaperOrderStatus.PARTIALLY_FILLED
                ),
                closed_at=executed_at if final else None,
                updated_at=executed_at,
            )
            try:
                stored_fill = unit_of_work.paper_fills.add(new_fill)
            except DuplicateRecordError:
                unit_of_work.rollback()
                raise PaperFillConflictError(order_id, sequence, "duplicate_record") from None
            try:
                updated_order = unit_of_work.paper_orders.transition_after_fill(transition)
            except (OptimisticConcurrencyError, PersistenceNotFoundError):
                unit_of_work.rollback()
                raise PaperOrderConcurrencyError(order_id) from None
            unit_of_work.commit()
        return PaperFillExecutionResult(stored_fill, updated_order)

    @staticmethod
    def _validate_fillable_order(order: StoredPaperOrder) -> None:
        if order.broker_code != INTERNAL_PAPER_BROKER_CODE:
            raise UnsupportedPaperOrderBrokerError(order.broker_code)
        if order.status not in {PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED}:
            raise PaperOrderNotFillableError(order.order_id, order.status)

    @staticmethod
    def _validate_accepted_intent(order_id: OrderID, intent: object) -> None:
        if not isinstance(intent, StoredTradeIntent):
            raise PaperFillSourceError(order_id, "trade_intent_contract")
        if (
            intent.currency != Currency("USD")
            or intent.side is not TradeSide.BUY
            or intent.order_type is not TradeOrderType.MARKET
            or intent.limit_price is not None
            or intent.time_in_force is not TimeInForce.DAY
            or intent.requested_quantity.value <= 0
        ):
            raise PaperFillSourceError(order_id, "accepted_request_shape_mismatch")
