"""Canonical source loading and validation for one position exit decision."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.paper_fills import StoredPaperFill
from auto_trading_v2.application.contracts.paper_orders import StoredPaperOrder
from auto_trading_v2.application.contracts.persistence import StoredMarketSnapshot
from auto_trading_v2.application.contracts.position_projection import (
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.contracts.trade_intents import StoredTradeIntent
from auto_trading_v2.application.ports.unit_of_work import UnitOfWork
from auto_trading_v2.application.position_exit_errors import (
    PositionExitPositionNotFoundError,
    PositionExitSnapshotNotFoundError,
    PositionExitSourceError,
    UnsupportedPositionExitCurrencyError,
)
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
)
from auto_trading_v2.domain.primitives import MarketSnapshotID, PositionID
from auto_trading_v2.domain.strategy_decisions import (
    PositionExitPolicy,
    StrategyAction,
    position_exit_policy_for,
)


@dataclass(frozen=True, slots=True)
class PositionExitSource:
    """Version-pinned canonical records required for one exit evaluation."""

    position: StoredPaperPosition
    event: StoredPositionEvent
    fill: StoredPaperFill
    order: StoredPaperOrder
    intent: StoredTradeIntent
    entry_decision: StoredCandidateStrategyDecision
    snapshot: StoredMarketSnapshot
    policy: PositionExitPolicy


def load_position_exit_source(
    unit_of_work: UnitOfWork,
    position_id: PositionID,
    market_snapshot_id: MarketSnapshotID,
    now: datetime,
) -> PositionExitSource:
    """Load the current version and reject any inconsistent canonical source."""

    position = unit_of_work.paper_positions.get(position_id)
    if position is None:
        raise PositionExitPositionNotFoundError(position_id)
    snapshot = unit_of_work.market_snapshots.get(market_snapshot_id)
    if snapshot is None:
        raise PositionExitSnapshotNotFoundError(market_snapshot_id)
    event = unit_of_work.position_events.get_by_position_sequence(
        position.position_id,
        position.version,
    )
    if event is None:
        raise _source_error(position_id, market_snapshot_id, "position_event_missing")
    fill = unit_of_work.paper_fills.get(event.fill_id)
    if fill is None:
        raise _source_error(position_id, market_snapshot_id, "paper_fill_missing")
    order = unit_of_work.paper_orders.get(fill.order_id)
    if order is None:
        raise _source_error(position_id, market_snapshot_id, "paper_order_missing")
    intent = unit_of_work.trade_intents.get(order.trade_intent_id)
    if intent is None:
        raise _source_error(position_id, market_snapshot_id, "trade_intent_missing")
    entry_decision = unit_of_work.strategy_decisions.get(intent.decision_id)
    if entry_decision is None:
        raise _source_error(position_id, market_snapshot_id, "entry_decision_missing")
    policy = position_exit_policy_for(
        entry_decision.strategy_id,
        entry_decision.strategy_version,
    )
    if policy is None:
        raise _source_error(position_id, market_snapshot_id, "unsupported_strategy_version")

    source = PositionExitSource(
        position,
        event,
        fill,
        order,
        intent,
        entry_decision,
        snapshot,
        policy,
    )
    validate_position_exit_source(source, now)
    return source


def validate_position_exit_source(source: PositionExitSource, now: datetime) -> None:
    """Validate version, source-chain identity, timestamps, and freshness."""

    position = source.position
    event = source.event
    snapshot = source.snapshot
    position_id = position.position_id
    snapshot_id = snapshot.market_snapshot_id

    if (
        position.status is not PaperPositionStatus.OPEN
        or position.quantity.value <= 0
        or position.closed_at is not None
        or position.version <= 0
    ):
        raise _source_error(position_id, snapshot_id, "position_not_open")
    if (
        event.position_id != position_id
        or event.sequence_no != position.version
        or event.quantity_after != position.quantity
        or event.average_cost_after != position.average_cost_price
        or event.realized_pnl_after != position.realized_pnl
        or event.occurred_at > position.updated_at
        or event.event_type not in {PositionEventType.OPENED, PositionEventType.INCREASED}
    ):
        raise _source_error(position_id, snapshot_id, "position_event_mismatch")
    if (
        event.fill_id != source.fill.fill_id
        or source.fill.order_id != source.order.order_id
        or source.order.trade_intent_id != source.intent.trade_intent_id
        or source.intent.decision_id != source.entry_decision.decision_id
        or event.occurred_at != source.fill.executed_at
    ):
        raise _source_error(position_id, snapshot_id, "source_identity_mismatch")
    if (
        source.entry_decision.action is not StrategyAction.ENTER_LONG
        or source.entry_decision.strategy_id != position.strategy_id
        or source.intent.symbol != position.symbol
        or source.intent.currency != position.currency
    ):
        raise _source_error(position_id, snapshot_id, "strategy_source_mismatch")
    if position.currency != source.policy.currency:
        raise UnsupportedPositionExitCurrencyError(position_id, position.currency)
    if snapshot.symbol != position.symbol:
        raise _source_error(position_id, snapshot_id, "symbol_mismatch")
    if snapshot.observed_at < position.updated_at or snapshot.observed_at < event.occurred_at:
        raise _source_error(position_id, snapshot_id, "snapshot_precedes_position")
    if snapshot.observed_at > now + source.policy.future_clock_skew_tolerance:
        raise _source_error(position_id, snapshot_id, "snapshot_too_far_in_future")
    if now - snapshot.observed_at > source.policy.snapshot_maximum_age:
        raise _source_error(position_id, snapshot_id, "snapshot_stale")


def _source_error(
    position_id: PositionID,
    market_snapshot_id: MarketSnapshotID,
    reason: str,
) -> PositionExitSourceError:
    return PositionExitSourceError(position_id, market_snapshot_id, reason)
