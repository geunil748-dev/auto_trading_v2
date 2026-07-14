from dataclasses import replace
from uuid import UUID

import pytest

from auto_trading_v2.application.errors import (
    CandidateNotFoundError,
    InvalidStrategyDecisionError,
    MarketSnapshotNotFoundError,
    RequiredStrategyDecisionMissingError,
    TradeIntentConflictError,
    TradeIntentRiskRejectedError,
)
from auto_trading_v2.domain.primitives import CandidateID
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from auto_trading_v2.domain.trade_intents import TimeInForce, TradeOrderType, TradeSide
from tests.unit.application.trade_intent_fakes import (
    CANDIDATE_ID,
    NOW,
    candidate,
    decision_batch,
    service_with,
    snapshot,
)

CASE_ACTIONS = (
    (
        StrategyAction.ENTER_LONG,
        StrategyAction.ENTER_LONG,
        StrategyAction.ENTER_LONG,
        StrategyAction.OBSERVE,
    ),
    (
        StrategyAction.SKIP,
        StrategyAction.ENTER_LONG,
        StrategyAction.ENTER_LONG,
        StrategyAction.OBSERVE,
    ),
    (
        StrategyAction.SKIP,
        StrategyAction.SKIP,
        StrategyAction.ENTER_LONG,
        StrategyAction.OBSERVE,
    ),
)


@pytest.mark.parametrize(("actions", "expected"), zip(CASE_ACTIONS, (3, 2, 1), strict=True))
def test_eligible_decisions_create_one_atomic_ordered_batch(
    actions: tuple[StrategyAction, ...],
    expected: int,
) -> None:
    service, unit_of_work, clock, id_factory = service_with(actions)

    result = service.create_all(CANDIDATE_ID)

    assert len(result.trade_intents) == expected
    assert clock.calls == 1
    assert id_factory.calls == expected
    assert len(unit_of_work.trade_intents.add_calls) == expected
    assert unit_of_work.commit_calls == 1
    assert unit_of_work.rollback_calls == 0
    assert all(item.created_at == NOW for item in result.trade_intents)
    assert all(item.requested_quantity.value == 40 for item in result.trade_intents)
    assert all(item.side is TradeSide.BUY for item in result.trade_intents)
    assert all(item.order_type is TradeOrderType.MARKET for item in result.trade_intents)
    assert all(item.time_in_force is TimeInForce.DAY for item in result.trade_intents)
    assert all(item.limit_price is None for item in result.trade_intents)


def test_no_eligible_decision_performs_no_sizing_clock_id_write_or_commit() -> None:
    actions = (
        StrategyAction.SKIP,
        StrategyAction.SKIP,
        StrategyAction.SKIP,
        StrategyAction.OBSERVE,
    )
    service, unit_of_work, clock, id_factory = service_with(actions)

    result = service.create_all(CANDIDATE_ID)

    assert result.trade_intents == ()
    assert clock.calls == 0
    assert id_factory.calls == 0
    assert unit_of_work.trade_intents.add_calls == []
    assert unit_of_work.commit_calls == 0


def test_candidate_and_snapshot_must_exist_before_decision_reads_or_writes() -> None:
    actions = CASE_ACTIONS[0]
    missing_candidate, candidate_uow, _, _ = service_with(
        actions,
        stored_candidate=candidate(),
    )
    candidate_uow.candidates.stored = None
    with pytest.raises(CandidateNotFoundError):
        missing_candidate.create_all(CANDIDATE_ID)

    missing_snapshot, snapshot_uow, _, _ = service_with(
        actions,
        stored_snapshot=snapshot(),
    )
    snapshot_uow.market_snapshots.stored = None
    with pytest.raises(MarketSnapshotNotFoundError):
        missing_snapshot.create_all(CANDIDATE_ID)
    assert snapshot_uow.trade_intents.add_calls == []


def test_all_four_required_decisions_are_validated_before_any_write() -> None:
    decisions = decision_batch(CASE_ACTIONS[0])[:-1]
    service, unit_of_work, clock, id_factory = service_with(
        CASE_ACTIONS[0],
        decisions=decisions,
    )

    with pytest.raises(RequiredStrategyDecisionMissingError):
        service.create_all(CANDIDATE_ID)

    assert clock.calls == 0
    assert id_factory.calls == 0
    assert unit_of_work.trade_intents.add_calls == []
    assert unit_of_work.commit_calls == 0


@pytest.mark.parametrize("invalid_source", ["candidate_mismatch", "duplicate_source"])
def test_mismatched_or_duplicate_source_is_rejected_before_write(
    invalid_source: str,
) -> None:
    decisions = decision_batch(CASE_ACTIONS[0])
    if invalid_source == "candidate_mismatch":
        decisions[0] = replace(decisions[0], candidate_id=CandidateID(UUID(int=999)))
    else:
        decisions.insert(1, decisions[0])
    service, unit_of_work, clock, id_factory = service_with(
        CASE_ACTIONS[0],
        decisions=decisions,
    )

    with pytest.raises(InvalidStrategyDecisionError):
        service.create_all(CANDIDATE_ID)

    assert clock.calls == id_factory.calls == 0
    assert unit_of_work.trade_intents.add_calls == []


@pytest.mark.parametrize(
    ("index", "action"),
    [
        (0, StrategyAction.OBSERVE),
        (3, StrategyAction.ENTER_LONG),
        (3, StrategyAction.SKIP),
    ],
)
def test_invalid_persisted_action_shape_is_rejected_before_write(
    index: int,
    action: StrategyAction,
) -> None:
    decisions = decision_batch(CASE_ACTIONS[0])
    decisions[index] = replace(decisions[index], action=action)
    service, unit_of_work, clock, id_factory = service_with(
        CASE_ACTIONS[0],
        decisions=decisions,
    )

    with pytest.raises(InvalidStrategyDecisionError):
        service.create_all(CANDIDATE_ID)

    assert clock.calls == id_factory.calls == 0
    assert unit_of_work.trade_intents.add_calls == []


def test_exit_long_source_is_rejected_without_recalculation_or_write() -> None:
    decisions = decision_batch(CASE_ACTIONS[0])
    object.__setattr__(decisions[0], "action", "EXIT_LONG")
    service, unit_of_work, clock, id_factory = service_with(
        CASE_ACTIONS[0],
        decisions=decisions,
    )

    with pytest.raises(InvalidStrategyDecisionError):
        service.create_all(CANDIDATE_ID)

    assert clock.calls == id_factory.calls == 0
    assert unit_of_work.trade_intents.add_calls == []


def test_risk_rejection_has_no_clock_id_write_or_commit() -> None:
    service, unit_of_work, clock, id_factory = service_with(CASE_ACTIONS[0])
    unit_of_work.market_snapshots.stored = snapshot("1000.000000000000000001")

    with pytest.raises(TradeIntentRiskRejectedError):
        service.create_all(CANDIDATE_ID)

    assert clock.calls == id_factory.calls == 0
    assert unit_of_work.trade_intents.add_calls == []
    assert unit_of_work.commit_calls == 0


def test_second_duplicate_rolls_back_first_and_stops_batch() -> None:
    service, unit_of_work, clock, id_factory = service_with(
        CASE_ACTIONS[0],
        failure_call=2,
    )

    with pytest.raises(TradeIntentConflictError):
        service.create_all(CANDIDATE_ID)

    assert clock.calls == 1
    assert id_factory.calls == 2
    assert len(unit_of_work.trade_intents.add_calls) == 2
    assert unit_of_work.trade_intents.pending == []
    assert unit_of_work.rollback_calls == 1
    assert unit_of_work.commit_calls == 0
