from dataclasses import replace
from uuid import UUID

from auto_trading_v2.domain.primitives import DecisionID, TradeIntentID
from auto_trading_v2.domain.trade_intents import (
    INITIAL_FIXED_USD_NOTIONAL_POLICY,
    trade_intent_idempotency_key,
)


def test_idempotency_key_has_exact_semantic_format() -> None:
    decision_id = DecisionID(UUID("11111111-1111-4111-8111-111111111111"))

    key = trade_intent_idempotency_key(decision_id)

    assert key == (
        "decision:11111111-1111-4111-8111-111111111111|intent-policy:fixed-usd-notional|version:v1"
    )
    assert len(key) <= 160
    assert not any(character.isspace() for character in key)


def test_key_changes_only_with_decision_or_policy_version() -> None:
    first = DecisionID(UUID(int=1))
    second = DecisionID(UUID(int=2))
    v2 = replace(INITIAL_FIXED_USD_NOTIONAL_POLICY, version="v2")

    assert trade_intent_idempotency_key(first) == trade_intent_idempotency_key(first)
    assert trade_intent_idempotency_key(first) != trade_intent_idempotency_key(second)
    assert trade_intent_idempotency_key(first) != trade_intent_idempotency_key(first, v2)
    assert str(TradeIntentID(UUID(int=3))) not in trade_intent_idempotency_key(first)
