"""Canonical source-chain loading for one Position projection."""

from dataclasses import dataclass
from decimal import Decimal

from auto_trading_v2.application.contracts.paper_fills import StoredPaperFill
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.persistence import (
    StoredCandidate,
    StoredMarketSnapshot,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.ports.unit_of_work import UnitOfWork
from auto_trading_v2.application.position_projection_errors import (
    InvalidPositionFillError,
    PositionFillNotFoundError,
    PositionProjectionSourceError,
    UnsupportedPositionFillSideError,
)
from auto_trading_v2.domain.paper_orders import (
    INTERNAL_PAPER_BROKER_CODE,
    PaperOrderStatus,
)
from auto_trading_v2.domain.primitives import FillID
from auto_trading_v2.domain.strategy_decisions import StrategyAction
from auto_trading_v2.domain.trade_intents import TradeSide


@dataclass(frozen=True, slots=True)
class ProjectionSource:
    """Canonical records required to identify one BUY position change."""

    fill: StoredPaperFill
    order: StoredPaperOrder
    intent: StoredTradeIntent
    decision: StoredCandidateStrategyDecision
    candidate: StoredCandidate
    snapshot: StoredMarketSnapshot


def load_projection_source(
    unit_of_work: UnitOfWork,
    fill_id: FillID,
) -> ProjectionSource:
    """Load and validate the complete Fill-to-snapshot source chain."""

    fill = unit_of_work.paper_fills.get(fill_id)
    if fill is None:
        raise PositionFillNotFoundError(fill_id)
    order = unit_of_work.paper_orders.get(fill.order_id)
    if order is None:
        raise PositionProjectionSourceError(fill_id, "paper_order_missing")
    intent = unit_of_work.trade_intents.get(order.trade_intent_id)
    if intent is None:
        raise PositionProjectionSourceError(fill_id, "trade_intent_missing")
    decision = unit_of_work.strategy_decisions.get(intent.decision_id)
    if decision is None:
        raise PositionProjectionSourceError(fill_id, "strategy_decision_missing")
    candidate = unit_of_work.candidates.get(decision.candidate_id)
    if candidate is None:
        raise PositionProjectionSourceError(fill_id, "candidate_missing")
    snapshot = unit_of_work.market_snapshots.get(candidate.market_snapshot_id)
    if snapshot is None:
        raise PositionProjectionSourceError(fill_id, "market_snapshot_missing")
    source = ProjectionSource(fill, order, intent, decision, candidate, snapshot)
    validate_projection_source(source)
    return source


def validate_projection_source(source: ProjectionSource) -> None:
    """Reject unsupported or inconsistent canonical values before any write."""

    fill_id = source.fill.fill_id
    if source.intent.side is not TradeSide.BUY:
        raise UnsupportedPositionFillSideError(fill_id, source.intent.side)
    if source.fill.quantity.value <= 0 or source.fill.price.value <= 0:
        raise InvalidPositionFillError(fill_id, "nonpositive_fill")
    if (
        source.order.order_id != source.fill.order_id
        or source.order.trade_intent_id != source.intent.trade_intent_id
        or source.intent.decision_id != source.decision.decision_id
        or source.decision.candidate_id != source.candidate.candidate_id
        or source.candidate.market_snapshot_id != source.snapshot.market_snapshot_id
    ):
        raise PositionProjectionSourceError(fill_id, "source_identity_mismatch")
    if (
        source.order.broker_code != INTERNAL_PAPER_BROKER_CODE
        or source.order.status not in {PaperOrderStatus.PARTIALLY_FILLED, PaperOrderStatus.FILLED}
        or source.order.accepted_at is None
    ):
        raise PositionProjectionSourceError(fill_id, "order_state_mismatch")
    if (
        source.intent.symbol != source.snapshot.symbol
        or source.fill.price != source.snapshot.last_price
        or source.fill.fee.currency != source.intent.currency
        or source.fill.fee.amount != Decimal("0")
        or source.decision.action is not StrategyAction.ENTER_LONG
        or source.fill.executed_at < source.order.accepted_at
    ):
        raise PositionProjectionSourceError(fill_id, "source_value_mismatch")
