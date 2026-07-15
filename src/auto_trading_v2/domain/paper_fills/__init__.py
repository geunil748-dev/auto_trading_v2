"""Deterministic canonical PaperFill domain policy."""

from auto_trading_v2.domain.paper_fills.errors import (
    PaperFillHistoryValidationError,
    PaperFillValidationError,
)
from auto_trading_v2.domain.paper_fills.execution_keys import paper_fill_execution_key
from auto_trading_v2.domain.paper_fills.history import FillHistoryEntry, validate_fill_history
from auto_trading_v2.domain.paper_fills.models import FillQuantityPlan
from auto_trading_v2.domain.paper_fills.policy import (
    INTERNAL_PAPER_SPLIT_FILL_POLICY,
    INTERNAL_PAPER_SPLIT_FILL_POLICY_NAME,
    INTERNAL_PAPER_SPLIT_FILL_POLICY_VERSION,
    InternalPaperSplitFillPolicy,
)
from auto_trading_v2.domain.paper_fills.transitions import validate_fill_transition

__all__ = [
    "INTERNAL_PAPER_SPLIT_FILL_POLICY",
    "INTERNAL_PAPER_SPLIT_FILL_POLICY_NAME",
    "INTERNAL_PAPER_SPLIT_FILL_POLICY_VERSION",
    "FillHistoryEntry",
    "FillQuantityPlan",
    "InternalPaperSplitFillPolicy",
    "PaperFillHistoryValidationError",
    "PaperFillValidationError",
    "paper_fill_execution_key",
    "validate_fill_history",
    "validate_fill_transition",
]
