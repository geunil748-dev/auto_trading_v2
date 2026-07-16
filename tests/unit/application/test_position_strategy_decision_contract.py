from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from auto_trading_v2.application.contracts.strategy_decisions import (
    NewPositionStrategyDecision,
    StoredPositionStrategyDecision,
)
from auto_trading_v2.domain.errors import ValidationError
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

POSITION_ID = PositionID(UUID("11111111-1111-4111-8111-111111111111"))
SNAPSHOT_ID = MarketSnapshotID(UUID("22222222-2222-4222-8222-222222222222"))
STRATEGY_ID = StrategyID(UUID("33333333-3333-4333-8333-333333333333"))


def decision(
    *,
    action: StrategyAction = StrategyAction.EXIT_LONG,
) -> NewPositionStrategyDecision:
    return NewPositionStrategyDecision(
        decision_id=DecisionID(uuid4()),
        decision_key=position_strategy_decision_key(
            POSITION_ID,
            SNAPSHOT_ID,
            STRATEGY_ID,
            "v1",
        ),
        position_id=POSITION_ID,
        position_version=1,
        market_snapshot_id=SNAPSHOT_ID,
        strategy_id=STRATEGY_ID,
        strategy_version="v1",
        action=action,
        reason_codes=("POSITION_EXIT_ALLOWED",),
        decided_at=datetime(2026, 7, 16, 15, tzinfo=timezone(timedelta(hours=9))),
    )


def test_position_contract_is_frozen_typed_and_normalizes_utc() -> None:
    value = decision()

    assert isinstance(value.position_id, PositionID)
    assert isinstance(value.market_snapshot_id, MarketSnapshotID)
    assert value.action is StrategyAction.EXIT_LONG
    assert value.decided_at == datetime(2026, 7, 16, 6, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        value.action = StrategyAction.SKIP  # type: ignore[misc]


@pytest.mark.parametrize("action", [StrategyAction.EXIT_LONG, StrategyAction.SKIP])
def test_position_contract_accepts_only_exit_or_skip(action: StrategyAction) -> None:
    assert decision(action=action).action is action


@pytest.mark.parametrize("action", [StrategyAction.ENTER_LONG, StrategyAction.OBSERVE])
def test_position_contract_rejects_candidate_actions(action: StrategyAction) -> None:
    with pytest.raises(ValidationError):
        decision(action=action)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("decision_id", uuid4()),
        ("position_id", uuid4()),
        ("position_version", 0),
        ("position_version", True),
        ("market_snapshot_id", uuid4()),
        ("strategy_id", uuid4()),
        ("decision_key", ""),
        ("decision_key", "has space"),
        ("strategy_version", ""),
        ("reason_codes", ()),
        ("reason_codes", ["NOT_A_TUPLE"]),
        ("decided_at", datetime(2026, 7, 16, 6)),
    ],
)
def test_position_contract_rejects_invalid_boundary_values(
    field: str,
    invalid: object,
) -> None:
    with pytest.raises(ValidationError):
        replace(decision(), **{field: invalid})


def test_stored_position_contract_adds_only_recorded_at() -> None:
    new = decision()
    stored = StoredPositionStrategyDecision(
        **{field.name: getattr(new, field.name) for field in fields(new)},
        recorded_at=datetime(2026, 7, 16, 7, tzinfo=UTC),
    )

    assert stored.recorded_at == datetime(2026, 7, 16, 7, tzinfo=UTC)
    names = {field.name for field in fields(stored)}
    assert "candidate_id" not in names
    assert "filter_evaluation_id" not in names
