"""Canonical paper-order repository boundary."""

from typing import Protocol

from auto_trading_v2.application.contracts.paper_orders import NewPaperOrder, StoredPaperOrder
from auto_trading_v2.domain.primitives import ClientOrderID, OrderID, TradeIntentID


class PaperOrderRepository(Protocol):
    def add(self, paper_order: NewPaperOrder) -> StoredPaperOrder: ...

    def get(self, order_id: OrderID) -> StoredPaperOrder | None: ...

    def get_by_trade_intent(self, trade_intent_id: TradeIntentID) -> StoredPaperOrder | None: ...

    def get_by_client_order_id(self, client_order_id: ClientOrderID) -> StoredPaperOrder | None: ...

    def get_by_broker_reference(
        self, *, broker_code: str, broker_order_ref: str
    ) -> StoredPaperOrder | None: ...
