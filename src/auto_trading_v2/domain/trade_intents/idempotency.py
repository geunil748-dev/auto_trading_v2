"""Semantic idempotency keys for canonical trade intents."""

from auto_trading_v2.domain.primitives import DecisionID
from auto_trading_v2.domain.trade_intents.errors import TradeIntentValidationError
from auto_trading_v2.domain.trade_intents.risk import (
    INITIAL_FIXED_USD_NOTIONAL_POLICY,
    FixedNotionalRiskPolicy,
)


def trade_intent_idempotency_key(
    decision_id: DecisionID,
    policy: FixedNotionalRiskPolicy = INITIAL_FIXED_USD_NOTIONAL_POLICY,
) -> str:
    """Build a stable decision-and-policy key with no random or temporal input."""

    if not isinstance(decision_id, DecisionID):
        raise TradeIntentValidationError("decision identifier is invalid")
    policy_segment = policy.name.casefold().replace("_", "-")
    key = (
        f"decision:{decision_id.serialize()}|intent-policy:{policy_segment}"
        f"|version:{policy.version}"
    )
    if len(key) > 160 or any(character.isspace() for character in key):
        raise TradeIntentValidationError("trade intent idempotency key is invalid")
    return key
