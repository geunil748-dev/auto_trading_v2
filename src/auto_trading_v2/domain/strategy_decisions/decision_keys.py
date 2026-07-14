"""Deterministic semantic keys for candidate strategy decisions."""

from auto_trading_v2.domain.primitives import CandidateID, StrategyID
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError
from auto_trading_v2.domain.strategy_decisions.models import validate_strategy_version


def candidate_strategy_decision_key(
    candidate_id: CandidateID,
    strategy_id: StrategyID,
    strategy_version: str,
) -> str:
    """Build the exact stable candidate/strategy/version key."""

    if not isinstance(candidate_id, CandidateID) or not isinstance(strategy_id, StrategyID):
        raise StrategyValidationError("decision key identifiers have invalid types")
    version = validate_strategy_version(strategy_version)
    key = (
        f"candidate:{candidate_id.serialize()}|strategy:{strategy_id.serialize()}|version:{version}"
    )
    if len(key) > 160 or any(character.isspace() for character in key):
        raise StrategyValidationError("decision key is invalid")
    return key
