"""Immutable application boundary contracts."""

from auto_trading_v2.application.contracts.paper_fills import (
    NewPaperFill,
    PaperFillExecutionResult,
    PaperOrderFillTransition,
    StoredPaperFill,
)
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
from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
    PositionProjectionResult,
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    NewPositionStrategyDecision,
    StoredCandidateStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import (
    NewTradeIntent,
    StoredTradeIntent,
)

__all__ = [
    "JSONValue",
    "NewCandidate",
    "NewCandidateStrategyDecision",
    "NewPositionStrategyDecision",
    "NewFilterEvaluation",
    "NewMarketSnapshot",
    "NewPaperOrder",
    "NewPaperFill",
    "NewPaperPosition",
    "NewPositionEvent",
    "NewTradeIntent",
    "PaperOrderSubmissionRequest",
    "PaperOrderSubmissionResult",
    "PaperFillExecutionResult",
    "PaperOrderFillTransition",
    "PaperPositionBuyTransition",
    "PositionProjectionResult",
    "StoredCandidate",
    "StoredCandidateStrategyDecision",
    "StoredPositionStrategyDecision",
    "StoredFilterEvaluation",
    "StoredMarketSnapshot",
    "StoredPaperOrder",
    "StoredPaperFill",
    "StoredPaperPosition",
    "StoredPositionEvent",
    "StoredTradeIntent",
]
