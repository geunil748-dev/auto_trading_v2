"""Immutable application contracts for canonical trade intents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    Currency,
    DecisionID,
    Price,
    Quantity,
    Symbol,
    TradeIntentID,
)
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.trade_intents.models import (
    TimeInForce,
    TradeOrderType,
    TradeSide,
)

IDEMPOTENCY_KEY_MAX_LENGTH = 160


def _require_instance(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{label} has an invalid type")


@dataclass(frozen=True, slots=True)
class NewTradeIntent:
    """Validated values accepted by a caller-owned persistence transaction."""

    trade_intent_id: TradeIntentID
    decision_id: DecisionID
    idempotency_key: str
    symbol: Symbol
    currency: Currency
    side: TradeSide
    order_type: TradeOrderType
    requested_quantity: Quantity
    limit_price: Price | None
    time_in_force: TimeInForce
    created_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.trade_intent_id, TradeIntentID, "trade_intent_id")
        _require_instance(self.decision_id, DecisionID, "decision_id")
        _require_instance(self.symbol, Symbol, "symbol")
        _require_instance(self.currency, Currency, "currency")
        _require_instance(self.side, TradeSide, "side")
        _require_instance(self.order_type, TradeOrderType, "order_type")
        _require_instance(self.requested_quantity, Quantity, "requested_quantity")
        _require_instance(self.time_in_force, TimeInForce, "time_in_force")
        if (
            not isinstance(self.idempotency_key, str)
            or not self.idempotency_key
            or self.idempotency_key != self.idempotency_key.strip()
            or len(self.idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH
            or any(character.isspace() for character in self.idempotency_key)
        ):
            raise ValidationError("idempotency_key is invalid")
        if self.requested_quantity.value <= 0:
            raise ValidationError("requested_quantity must be positive")
        if self.order_type is TradeOrderType.MARKET and self.limit_price is not None:
            raise ValidationError("MARKET intent must not have a limit price")
        if self.order_type is TradeOrderType.LIMIT and not isinstance(self.limit_price, Price):
            raise ValidationError("LIMIT intent requires a valid limit price")
        object.__setattr__(self, "created_at", normalize_utc(self.created_at))


@dataclass(frozen=True, slots=True)
class StoredTradeIntent(NewTradeIntent):
    """Canonical trade intent including its database recording time."""

    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredTradeIntent, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))
