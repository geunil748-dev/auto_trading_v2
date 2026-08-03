"""Atomic submission of one canonical TradeIntent to a PaperBroker."""

from __future__ import annotations

from dataclasses import dataclass

from auto_trading_v2.application.contracts.paper_orders import (
    NewPaperOrder,
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
    StoredPaperOrder,
)
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    InvalidPaperBrokerResultError,
    PaperOrderConflictError,
    PaperOrderSubmissionError,
    TradeIntentNotFoundError,
)
from auto_trading_v2.application.ports.id_factory import ClientOrderIDFactory, OrderIDFactory
from auto_trading_v2.application.ports.paper_broker import PaperBroker, PaperBrokerError
from auto_trading_v2.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from auto_trading_v2.domain.paper_orders import (
    PaperBrokerSubmissionOutcome,
    PaperOrderStatus,
)
from auto_trading_v2.domain.primitives import TradeIntentID
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class PaperOrderSubmissionService:
    """Submit and persist exactly one initial ACCEPTED or REJECTED order."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    order_id_factory: OrderIDFactory
    client_order_id_factory: ClientOrderIDFactory
    broker: PaperBroker

    def submit(self, trade_intent_id: TradeIntentID) -> StoredPaperOrder:
        """Submit the stored intent once within an explicit persistence transaction."""

        with self.unit_of_work_factory() as unit_of_work:
            trade_intent = unit_of_work.trade_intents.get(trade_intent_id)
            if trade_intent is None:
                raise TradeIntentNotFoundError(trade_intent_id)
            if unit_of_work.paper_orders.get_by_trade_intent(trade_intent_id) is not None:
                raise PaperOrderConflictError(trade_intent_id, "trade_intent_exists")

            client_order_id = self.client_order_id_factory.for_trade_intent(trade_intent_id)
            if unit_of_work.paper_orders.get_by_client_order_id(client_order_id) is not None:
                raise PaperOrderConflictError(trade_intent_id, "client_order_id_exists")

            request = PaperOrderSubmissionRequest(
                trade_intent_id=trade_intent.trade_intent_id,
                client_order_id=client_order_id,
                symbol=trade_intent.symbol,
                currency=trade_intent.currency,
                side=trade_intent.side,
                order_type=trade_intent.order_type,
                requested_quantity=trade_intent.requested_quantity,
                limit_price=trade_intent.limit_price,
                time_in_force=trade_intent.time_in_force,
                submitted_at=self.clock.now_utc(),
            )
            try:
                result = self.broker.submit(request)
            except PaperBrokerError as exc:
                unit_of_work.rollback()
                raise PaperOrderSubmissionError(self.broker.broker_code, exc.category) from None

            self._validate_result_or_rollback(unit_of_work, request, result)
            if (
                result.broker_order_ref is not None
                and unit_of_work.paper_orders.get_by_broker_reference(
                    broker_code=result.broker_code,
                    broker_order_ref=result.broker_order_ref,
                )
                is not None
            ):
                raise PaperOrderConflictError(trade_intent_id, "broker_reference_exists")

            paper_order = self._new_order(request, result)
            try:
                stored = unit_of_work.paper_orders.add(paper_order)
            except DuplicateRecordError:
                unit_of_work.rollback()
                raise PaperOrderConflictError(trade_intent_id, "duplicate_record") from None
            unit_of_work.commit()
        return stored

    def _validate_result_or_rollback(
        self,
        unit_of_work: UnitOfWork,
        request: PaperOrderSubmissionRequest,
        result: object,
    ) -> None:
        reason: str | None = None
        if not isinstance(result, PaperOrderSubmissionResult):
            reason = "invalid_contract"
        elif result.broker_code != self.broker.broker_code:
            reason = "broker_code_mismatch"
        elif result.processed_at < request.submitted_at:
            reason = "processed_at_precedes_submission"
        if reason is not None:
            unit_of_work.rollback()
            raise InvalidPaperBrokerResultError(self.broker.broker_code, reason)

    def _new_order(
        self,
        request: PaperOrderSubmissionRequest,
        result: PaperOrderSubmissionResult,
    ) -> NewPaperOrder:
        accepted = result.outcome is PaperBrokerSubmissionOutcome.ACCEPTED
        return NewPaperOrder(
            order_id=self.order_id_factory.new(),
            trade_intent_id=request.trade_intent_id,
            client_order_id=request.client_order_id,
            broker_code=result.broker_code,
            broker_order_ref=result.broker_order_ref,
            status=PaperOrderStatus.ACCEPTED if accepted else PaperOrderStatus.REJECTED,
            rejection_code=result.rejection_code,
            submitted_at=request.submitted_at,
            accepted_at=result.processed_at if accepted else None,
            closed_at=None if accepted else result.processed_at,
            version=1,
            updated_at=result.processed_at,
        )
