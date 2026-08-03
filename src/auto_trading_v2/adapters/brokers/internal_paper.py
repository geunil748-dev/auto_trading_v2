"""Pure deterministic internal paper-broker adapter."""

from auto_trading_v2.application.contracts.paper_orders import (
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
)
from auto_trading_v2.domain.paper_orders import (
    INTERNAL_PAPER_BROKER_CODE,
    PaperBrokerSubmissionOutcome,
    internal_paper_broker_reference,
)
from auto_trading_v2.domain.primitives import Currency
from auto_trading_v2.domain.trade_intents import TradeOrderType, TradeSide

UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"
UNSUPPORTED_SIDE = "UNSUPPORTED_SIDE"
UNSUPPORTED_ORDER_TYPE = "UNSUPPORTED_ORDER_TYPE"


class InternalPaperBroker:
    """Accept the initial V2 request shape and deterministically reject others."""

    @property
    def broker_code(self) -> str:
        return INTERNAL_PAPER_BROKER_CODE

    def submit(self, request: PaperOrderSubmissionRequest) -> PaperOrderSubmissionResult:
        reference = internal_paper_broker_reference(request.client_order_id)
        rejection_code: str | None = None
        if request.currency != Currency("USD"):
            rejection_code = UNSUPPORTED_CURRENCY
        elif request.side is not TradeSide.BUY:
            rejection_code = UNSUPPORTED_SIDE
        elif request.order_type is not TradeOrderType.MARKET:
            rejection_code = UNSUPPORTED_ORDER_TYPE

        outcome = (
            PaperBrokerSubmissionOutcome.ACCEPTED
            if rejection_code is None
            else PaperBrokerSubmissionOutcome.REJECTED
        )
        return PaperOrderSubmissionResult(
            outcome=outcome,
            broker_code=self.broker_code,
            broker_order_ref=reference,
            processed_at=request.submitted_at,
            rejection_code=rejection_code,
        )
