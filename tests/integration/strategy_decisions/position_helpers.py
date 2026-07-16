"""Builders for position strategy-decision persistence tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Engine

from auto_trading_v2.application.contracts.strategy_decisions import (
    NewPositionStrategyDecision,
)
from auto_trading_v2.domain.primitives import (
    DecisionID,
    MarketSnapshotID,
    PositionID,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions import (
    StrategyAction,
    position_strategy_decision_key,
)
from tests.integration.persistence.records import insert_canonical_graph

DECIDED_AT = datetime(2026, 7, 16, 6, 30, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class PositionDecisionSource:
    position_id: PositionID
    market_snapshot_id: MarketSnapshotID
    strategy_id: StrategyID
    candidate_decision_id: DecisionID


def prepare_position_source(engine: Engine) -> PositionDecisionSource:
    with engine.begin() as connection:
        ids = insert_canonical_graph(connection)
    return PositionDecisionSource(
        position_id=PositionID(_uuid(ids["position_id"])),
        market_snapshot_id=MarketSnapshotID(_uuid(ids["market_snapshot_id"])),
        strategy_id=StrategyID(_uuid(ids["strategy_id"])),
        candidate_decision_id=DecisionID(_uuid(ids["decision_id"])),
    )


def new_position_decision(
    source: PositionDecisionSource,
    *,
    decision_id: DecisionID | None = None,
    decision_key: str | None = None,
    market_snapshot_id: MarketSnapshotID | None = None,
    strategy_id: StrategyID | None = None,
    strategy_version: str = "v1",
    action: StrategyAction = StrategyAction.EXIT_LONG,
) -> NewPositionStrategyDecision:
    snapshot_id = market_snapshot_id or source.market_snapshot_id
    effective_strategy_id = strategy_id or source.strategy_id
    return NewPositionStrategyDecision(
        decision_id=decision_id or DecisionID(uuid4()),
        decision_key=decision_key
        or position_strategy_decision_key(
            source.position_id,
            snapshot_id,
            effective_strategy_id,
            strategy_version,
        ),
        position_id=source.position_id,
        position_version=1,
        market_snapshot_id=snapshot_id,
        strategy_id=effective_strategy_id,
        strategy_version=strategy_version,
        action=action,
        reason_codes=("POSITION_EXIT_ALLOWED",),
        decided_at=DECIDED_AT,
    )


def _uuid(value: object) -> UUID:
    assert isinstance(value, UUID)
    return value
