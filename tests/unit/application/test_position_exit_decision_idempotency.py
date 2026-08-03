from datetime import timedelta
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.position_exit_decisions import (
    PositionExitDecisionOutcome,
)
from auto_trading_v2.application.position_exit_errors import (
    PositionExitPersistenceError,
    PositionExitSourceError,
)
from auto_trading_v2.domain.primitives import MarketSnapshotID

from .position_exit_fakes import (
    FakeUnitOfWork,
    assert_no_write,
    service_for,
)
from .position_exit_records import (
    NOW,
    POSITION_ID,
    SNAPSHOT_ID,
    exit_decision,
    snapshot,
)


def test_same_snapshot_returns_existing_without_new_id_or_write() -> None:
    existing = exit_decision()
    source = FakeUnitOfWork(existing_exit=existing)
    service, _, clock, ids = service_for(source)

    result = service.decide(POSITION_ID, SNAPSHOT_ID)

    assert result.outcome is PositionExitDecisionOutcome.ALREADY_DECIDED
    assert result.decision == existing
    assert result.return_rate is result.holding_duration is None
    assert source.strategy_decisions.add_calls == []
    assert source.commit_calls == ids.calls == 0
    assert clock.calls == 1


def test_different_snapshot_creates_a_distinct_decision() -> None:
    other_snapshot_id = MarketSnapshotID(UUID(int=101))
    source = FakeUnitOfWork(
        stored_snapshot=snapshot(market_snapshot_id=other_snapshot_id),
    )
    service, _, _, ids = service_for(source)

    result = service.decide(POSITION_ID, other_snapshot_id)

    assert result.outcome is PositionExitDecisionOutcome.CREATED
    assert result.market_snapshot_id == other_snapshot_id
    assert ids.calls == 1


def test_duplicate_race_resolves_only_from_exact_fresh_lookup() -> None:
    first = FakeUnitOfWork()
    first.strategy_decisions.duplicate_constraint = "ix_strategy_decisions_position_snapshot_unique"
    second = FakeUnitOfWork(existing_exit=exit_decision())
    service, factory, clock, _ = service_for(first, second)

    result = service.decide(POSITION_ID, SNAPSHOT_ID)

    assert result.outcome is PositionExitDecisionOutcome.ALREADY_DECIDED
    assert factory.calls == 2
    assert clock.calls == 1
    assert first.rollback_calls == second.rollback_calls == 1


def test_unrelated_duplicate_is_not_misclassified() -> None:
    first = FakeUnitOfWork()
    first.strategy_decisions.duplicate_constraint = "uq_unrelated"
    second = FakeUnitOfWork()
    service, _, _, _ = service_for(first, second)

    with pytest.raises(PositionExitPersistenceError, match="uq_unrelated"):
        service.decide(POSITION_ID, SNAPSHOT_ID)


def test_error_paths_leave_all_source_records_unchanged() -> None:
    source = FakeUnitOfWork(
        stored_snapshot=snapshot(observed_at=NOW - timedelta(minutes=10)),
    )
    before = (
        source.paper_positions.value,
        source.position_events.value,
        source.paper_fills.value,
        source.paper_orders.value,
        source.trade_intents.value,
        source.strategy_decisions.entry,
        source.market_snapshots.value,
    )
    service, _, clock, ids = service_for(source)

    with pytest.raises(PositionExitSourceError):
        service.decide(POSITION_ID, SNAPSHOT_ID)

    after = (
        source.paper_positions.value,
        source.position_events.value,
        source.paper_fills.value,
        source.paper_orders.value,
        source.trade_intents.value,
        source.strategy_decisions.entry,
        source.market_snapshots.value,
    )
    assert after == before
    assert source.rollback_calls == clock.calls == 1
    assert_no_write(source, ids)
