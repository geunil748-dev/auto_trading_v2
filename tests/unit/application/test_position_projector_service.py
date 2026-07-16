from dataclasses import replace
from decimal import Decimal
from inspect import signature

import pytest

from auto_trading_v2.application.position_projection_errors import (
    PositionFillNotFoundError,
    PositionNotFoundDuringTransitionError,
    PositionProjectionConcurrencyError,
    PositionProjectionPersistenceError,
    PositionProjectionSourceError,
    UnsupportedPositionFillSideError,
)
from auto_trading_v2.application.services.position_projector import PositionProjectorService
from auto_trading_v2.domain.position_projection import (
    PositionEventType,
    ProjectionOutcome,
)
from auto_trading_v2.domain.primitives import (
    PositionEventID,
    PositionID,
    Price,
    Quantity,
)
from auto_trading_v2.domain.trade_intents import TradeSide

from .paper_fill_fakes import fill, intent, snapshot
from .position_projector_fakes import (
    FILL_ID,
    POSITION_EVENT_ID,
    POSITION_ID,
    FakeUnitOfWork,
    FakeUnitOfWorkFactory,
    event,
    position,
)


class CountingPositionIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> PositionID:
        self.calls += 1
        return POSITION_ID


class CountingPositionEventIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> PositionEventID:
        self.calls += 1
        return POSITION_EVENT_ID


def service_for(
    *unit_of_works: FakeUnitOfWork,
) -> tuple[
    PositionProjectorService,
    FakeUnitOfWorkFactory,
    CountingPositionIDFactory,
    CountingPositionEventIDFactory,
]:
    factory = FakeUnitOfWorkFactory(*unit_of_works)
    position_ids = CountingPositionIDFactory()
    event_ids = CountingPositionEventIDFactory()
    service = PositionProjectorService(factory, position_ids, event_ids)
    return service, factory, position_ids, event_ids


def assert_no_writes(
    unit_of_work: FakeUnitOfWork,
    position_ids: CountingPositionIDFactory,
    event_ids: CountingPositionEventIDFactory,
) -> None:
    assert unit_of_work.paper_positions.add_calls == []
    assert unit_of_work.paper_positions.transition_calls == []
    assert unit_of_work.position_events.add_calls == []
    assert unit_of_work.commit_calls == 0
    assert position_ids.calls == event_ids.calls == 0


def test_public_input_is_only_fill_id() -> None:
    assert tuple(signature(PositionProjectorService.project_fill).parameters) == (
        "self",
        "fill_id",
    )


def test_missing_fill_stops_before_source_identity_or_write() -> None:
    unit_of_work = FakeUnitOfWork(fill_present=False)
    service, _, position_ids, event_ids = service_for(unit_of_work)

    with pytest.raises(PositionFillNotFoundError):
        service.project_fill(FILL_ID)

    assert unit_of_work.paper_orders.calls == 0
    assert_no_writes(unit_of_work, position_ids, event_ids)


@pytest.mark.parametrize(
    ("missing_source", "reason"),
    [
        ("order", "paper_order_missing"),
        ("intent", "trade_intent_missing"),
        ("decision", "strategy_decision_missing"),
        ("candidate", "candidate_missing"),
        ("snapshot", "market_snapshot_missing"),
    ],
)
def test_missing_source_chain_has_no_writes(
    missing_source: str,
    reason: str,
) -> None:
    unit_of_work = FakeUnitOfWork(missing_source=missing_source)
    service, _, position_ids, event_ids = service_for(unit_of_work)

    with pytest.raises(PositionProjectionSourceError, match=reason):
        service.project_fill(FILL_ID)

    assert_no_writes(unit_of_work, position_ids, event_ids)


def test_sell_source_is_explicitly_rejected_without_write() -> None:
    unit_of_work = FakeUnitOfWork(
        stored_intent=replace(intent(), side=TradeSide.SELL),
    )
    service, _, position_ids, event_ids = service_for(unit_of_work)

    with pytest.raises(UnsupportedPositionFillSideError):
        service.project_fill(FILL_ID)

    assert_no_writes(unit_of_work, position_ids, event_ids)


def test_source_price_mismatch_is_rejected_before_write() -> None:
    unit_of_work = FakeUnitOfWork(
        stored_fill=replace(fill(), price=Price(Decimal("130"))),
    )
    service, _, position_ids, event_ids = service_for(unit_of_work)

    with pytest.raises(PositionProjectionSourceError, match="source_value_mismatch"):
        service.project_fill(FILL_ID)

    assert_no_writes(unit_of_work, position_ids, event_ids)


def test_first_buy_creates_open_position_then_opened_event_and_commits() -> None:
    unit_of_work = FakeUnitOfWork()
    service, _, position_ids, event_ids = service_for(unit_of_work)

    result = service.project_fill(FILL_ID)

    assert result.outcome is ProjectionOutcome.APPLIED
    assert result.event_type is PositionEventType.OPENED
    assert result.quantity == Quantity(20)
    assert result.average_cost_price == Price(Decimal("25.000000000000000000"))
    assert result.position_version == 1
    assert unit_of_work.operations == ["position_add", "event_add"]
    created = unit_of_work.paper_positions.add_calls[0]
    created_event = unit_of_work.position_events.add_calls[0]
    assert created.opened_at == created.updated_at == fill().executed_at
    assert created.version == created_event.sequence_no == 1
    assert created_event.quantity_delta == fill().quantity
    assert unit_of_work.commit_calls == 1
    assert position_ids.calls == event_ids.calls == 1


def test_followup_buy_inserts_event_then_optimistically_increases_position() -> None:
    source_fill = replace(
        fill(),
        quantity=Quantity(5),
        price=Price(Decimal("130")),
    )
    source_snapshot = replace(snapshot(), last_price=Price(Decimal("130")))
    existing = position()
    unit_of_work = FakeUnitOfWork(
        stored_fill=source_fill,
        stored_snapshot=source_snapshot,
        stored_position=existing,
    )
    service, _, position_ids, event_ids = service_for(unit_of_work)

    result = service.project_fill(FILL_ID)

    assert result.outcome is ProjectionOutcome.APPLIED
    assert result.event_type is PositionEventType.INCREASED
    assert result.quantity == Quantity(15)
    assert result.average_cost_price == Price(Decimal("110.000000000000000000"))
    assert result.position_version == 2
    assert unit_of_work.operations == ["event_add", "position_transition"]
    transition = unit_of_work.paper_positions.transition_calls[0]
    assert transition.expected_version == 1
    assert transition.quantity == Quantity(15)
    assert transition.updated_at == source_fill.executed_at
    assert unit_of_work.paper_positions.value is not None
    assert unit_of_work.paper_positions.value.opened_at == existing.opened_at
    assert unit_of_work.paper_positions.value.version == 2
    assert position_ids.calls == 0
    assert event_ids.calls == unit_of_work.commit_calls == 1


def test_reapplying_fill_returns_already_applied_without_source_or_write() -> None:
    existing_event = event()
    unit_of_work = FakeUnitOfWork(stored_event=existing_event)
    service, _, position_ids, event_ids = service_for(unit_of_work)

    result = service.project_fill(FILL_ID)

    assert result.outcome is ProjectionOutcome.ALREADY_APPLIED
    assert result.position_event_id == existing_event.position_event_id
    assert unit_of_work.paper_fills.calls == 0
    assert_no_writes(unit_of_work, position_ids, event_ids)


def test_same_fill_open_position_race_resolves_from_committed_event() -> None:
    first = FakeUnitOfWork()
    first.paper_positions.add_duplicate_constraint = "ix_paper_positions_open_unique"
    second = FakeUnitOfWork(stored_event=event())
    service, factory, _, _ = service_for(first, second)

    result = service.project_fill(FILL_ID)

    assert result.outcome is ProjectionOutcome.ALREADY_APPLIED
    assert factory.calls == 2
    assert first.rollback_calls == second.rollback_calls == 1


def test_same_fill_event_race_resolves_only_when_fill_event_exists() -> None:
    first = FakeUnitOfWork(stored_position=position())
    first.position_events.duplicate_constraint = "uq_position_events_fill_id"
    second = FakeUnitOfWork(stored_event=event())
    service, _, _, _ = service_for(first, second)

    result = service.project_fill(FILL_ID)

    assert result.outcome is ProjectionOutcome.ALREADY_APPLIED
    assert first.operations == ["event_add"]
    assert first.paper_positions.transition_calls == []
    assert first.rollback_calls == 1


def test_unrelated_duplicate_is_not_misclassified_as_already_applied() -> None:
    first = FakeUnitOfWork(stored_position=position())
    first.position_events.duplicate_constraint = "uq_unrelated"
    second = FakeUnitOfWork()
    service, _, _, _ = service_for(first, second)

    with pytest.raises(PositionProjectionPersistenceError, match="uq_unrelated"):
        service.project_fill(FILL_ID)


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        ("stale", PositionProjectionConcurrencyError),
        ("missing", PositionNotFoundDuringTransitionError),
    ],
)
def test_transition_failure_rolls_back_pending_event(
    failure: str,
    error_type: type[Exception],
) -> None:
    unit_of_work = FakeUnitOfWork(stored_position=position())
    unit_of_work.paper_positions.transition_failure = failure
    service, _, _, _ = service_for(unit_of_work)

    with pytest.raises(error_type):
        service.project_fill(FILL_ID)

    assert unit_of_work.operations == ["event_add", "position_transition"]
    assert unit_of_work.position_events.existing is None
    assert unit_of_work.commit_calls == 0
    assert unit_of_work.rollback_calls == 1


def test_position_sequence_conflict_rolls_back_without_transition() -> None:
    first = FakeUnitOfWork(stored_position=position())
    first.position_events.duplicate_constraint = "uq_position_events_position_sequence"
    second = FakeUnitOfWork()
    service, _, _, _ = service_for(first, second)

    with pytest.raises(PositionProjectionConcurrencyError):
        service.project_fill(FILL_ID)

    assert first.operations == ["event_add"]
    assert first.paper_positions.transition_calls == []
    assert first.rollback_calls == 1
