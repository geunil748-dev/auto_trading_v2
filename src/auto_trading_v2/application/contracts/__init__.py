"""Immutable application boundary contracts."""

from auto_trading_v2.application.contracts.paper_orders import (
    NewPaperOrder,
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
    StoredPaperOrder,
)
from auto_trading_v2.application.contracts.persistence import (
    JSONValue,
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
    StoredCandidate,
    StoredFilterEvaluation,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)

__all__ = [
    "JSONValue",
    "NewCandidate",
    "NewCandidateStrategyDecision",
    "NewFilterEvaluation",
    "NewMarketSnapshot",
    "NewPaperOrder",
    "NewTradeIntent",
    "PaperOrderSubmissionRequest",
    "PaperOrderSubmissionResult",
    "StoredCandidate",
    "StoredCandidateStrategyDecision",
    "StoredFilterEvaluation",
    "StoredMarketSnapshot",
    "StoredPaperOrder",
    "StoredTradeIntent",
]
