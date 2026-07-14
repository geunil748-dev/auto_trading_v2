"""Canonical trade-intent repository boundary."""

from typing import Protocol

from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)
from auto_trading_v2.domain.primitives import DecisionID, TradeIntentID


class TradeIntentRepository(Protocol):
    def add(self, trade_intent: NewTradeIntent) -> StoredTradeIntent: ...

    def get(self, trade_intent_id: TradeIntentID) -> StoredTradeIntent | None: ...

    def get_by_decision(self, decision_id: DecisionID) -> StoredTradeIntent | None: ...

    def get_by_idempotency_key(self, idempotency_key: str) -> StoredTradeIntent | None: ...
