from decimal import Decimal

import pytest

from auto_trading_v2.application.errors import (
    InvalidPaperFillHistoryError,
    PaperFillConflictError,
    PaperFillSourceError,
    PaperOrderConcurrencyError,
    PaperOrderNotFillableError,
    PaperOrderNotFoundError,
    UnsupportedPaperOrderBrokerError,
)
from auto_trading_v2.application.services.paper_fill import PaperFillExecutionService
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import Currency, Quantity, Symbol

from .paper_fill_fakes import (
    EXECUTED_AT,
    ORDER_ID,
    CountingClock,
    CountingFillIDFactory,
    FakeUnitOfWork,
    fill,
    intent,
    order,
    snapshot,
)


def dependencies(
    **kwargs: object,
) -> tuple[PaperFillExecutionService, FakeUnitOfWork, CountingClock, CountingFillIDFactory]:
    unit_of_work = FakeUnitOfWork(**kwargs)  # type: ignore[arg-type]
    clock = CountingClock()
    fill_ids = CountingFillIDFactory()
    service = PaperFillExecutionService(lambda: unit_of_work, clock, fill_ids)
    return service, unit_of_work, clock, fill_ids


def assert_no_execution_writes(uow: object, clock: object, fill_ids: object) -> None:
    assert clock.calls == 0  # type: ignore[attr-defined]
    assert fill_ids.calls == 0  # type: ignore[attr-defined]
    assert uow.paper_fills.add_calls == []  # type: ignore[attr-defined]
    assert uow.paper_orders.transition_calls == []  # type: ignore[attr-defined]
    assert uow.commit_calls == 0  # type: ignore[attr-defined]


def test_missing_order_stops_before_source_lookup_or_effects() -> None:
    service, uow, clock, fill_ids = dependencies(order_present=False)

    with pytest.raises(PaperOrderNotFoundError):
        service.execute_next(ORDER_ID)

    assert uow.paper_orders.calls == 1
    assert uow.trade_intents.calls == 0
    assert_no_execution_writes(uow, clock, fill_ids)


@pytest.mark.parametrize("status", [PaperOrderStatus.REJECTED, PaperOrderStatus.FILLED])
def test_non_fillable_order_reexecution_has_no_source_or_effects(
    status: PaperOrderStatus,
) -> None:
    service, uow, clock, fill_ids = dependencies(stored_order=order(status))

    with pytest.raises(PaperOrderNotFillableError):
        service.execute_next(ORDER_ID)

    assert uow.trade_intents.calls == 0
    assert_no_execution_writes(uow, clock, fill_ids)


def test_wrong_broker_is_rejected_before_source_or_effects() -> None:
    service, uow, clock, fill_ids = dependencies(stored_order=order(broker_code="UNSUPPORTED"))

    with pytest.raises(UnsupportedPaperOrderBrokerError):
        service.execute_next(ORDER_ID)

    assert uow.trade_intents.calls == 0
    assert_no_execution_writes(uow, clock, fill_ids)


@pytest.mark.parametrize(
    ("missing_source", "reason"),
    [
        ("intent", "trade_intent_missing"),
        ("decision", "strategy_decision_missing"),
        ("candidate", "candidate_missing"),
        ("snapshot", "market_snapshot_missing"),
    ],
)
def test_missing_canonical_source_has_no_time_identity_or_write(
    missing_source: str,
    reason: str,
) -> None:
    service, uow, clock, fill_ids = dependencies(missing_source=missing_source)

    with pytest.raises(PaperFillSourceError, match=reason):
        service.execute_next(ORDER_ID)

    assert_no_execution_writes(uow, clock, fill_ids)


def test_symbol_mismatch_and_request_shape_mismatch_have_no_effects() -> None:
    for kwargs, reason in (
        ({"stored_snapshot": snapshot(symbol=Symbol("MSFT"))}, "symbol_mismatch"),
        ({"stored_intent": intent(currency=Currency("KRW"))}, "accepted_request_shape_mismatch"),
    ):
        service, uow, clock, fill_ids = dependencies(**kwargs)

        with pytest.raises(PaperFillSourceError, match=reason):
            service.execute_next(ORDER_ID)

        assert_no_execution_writes(uow, clock, fill_ids)


def test_quantity_one_creates_one_fill_and_directly_fills_order() -> None:
    service, uow, clock, fill_ids = dependencies(stored_intent=intent(1))

    result = service.execute_next(ORDER_ID)

    assert clock.calls == fill_ids.calls == 1
    assert len(uow.paper_fills.add_calls) == len(uow.paper_orders.transition_calls) == 1
    created = uow.paper_fills.add_calls[0]
    transition = uow.paper_orders.transition_calls[0]
    assert created.fill_sequence == created.quantity.value == 1
    assert created.price.value == Decimal("25")
    assert created.fee.amount == Decimal("0")
    assert transition.new_status is PaperOrderStatus.FILLED
    assert transition.closed_at == transition.updated_at == EXECUTED_AT
    assert result.paper_order.status is PaperOrderStatus.FILLED
    assert result.paper_order.version == 2
    assert uow.commit_calls == 1


def test_first_split_fill_is_partial_and_preserves_open_order() -> None:
    service, uow, clock, fill_ids = dependencies(stored_intent=intent(41))

    result = service.execute_next(ORDER_ID)

    created = uow.paper_fills.add_calls[0]
    transition = uow.paper_orders.transition_calls[0]
    assert clock.calls == fill_ids.calls == 1
    assert created.fill_sequence == 1
    assert created.quantity == Quantity(20)
    assert transition.expected_status is PaperOrderStatus.ACCEPTED
    assert transition.expected_version == 1
    assert transition.new_status is PaperOrderStatus.PARTIALLY_FILLED
    assert transition.closed_at is None
    assert result.paper_order.version == 2
    assert uow.commit_calls == 1


def test_second_split_fill_completes_remaining_quantity() -> None:
    partial = order(PaperOrderStatus.PARTIALLY_FILLED, version=2)
    service, uow, clock, fill_ids = dependencies(
        stored_order=partial,
        stored_intent=intent(41),
        fills=(fill(quantity=20),),
    )

    result = service.execute_next(ORDER_ID)

    created = uow.paper_fills.add_calls[0]
    transition = uow.paper_orders.transition_calls[0]
    assert clock.calls == fill_ids.calls == 1
    assert created.fill_sequence == 2
    assert created.quantity == Quantity(21)
    assert transition.expected_status is PaperOrderStatus.PARTIALLY_FILLED
    assert transition.expected_version == 2
    assert transition.new_status is PaperOrderStatus.FILLED
    assert transition.closed_at == EXECUTED_AT
    assert result.paper_order.version == 3
    assert uow.commit_calls == 1


def test_invalid_existing_history_stops_before_time_identity_or_write() -> None:
    partial = order(PaperOrderStatus.PARTIALLY_FILLED, version=2)
    service, uow, clock, fill_ids = dependencies(
        stored_order=partial,
        fills=(fill(quantity=19),),
    )

    with pytest.raises(InvalidPaperFillHistoryError):
        service.execute_next(ORDER_ID)

    assert_no_execution_writes(uow, clock, fill_ids)


def test_duplicate_fill_rolls_back_without_transition_or_commit() -> None:
    service, uow, clock, fill_ids = dependencies()
    uow.paper_fills.duplicate = True

    with pytest.raises(PaperFillConflictError, match="duplicate_record"):
        service.execute_next(ORDER_ID)

    assert clock.calls == fill_ids.calls == 1
    assert len(uow.paper_fills.add_calls) == 1
    assert uow.paper_orders.transition_calls == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_stale_order_transition_rolls_back_insert_without_commit() -> None:
    service, uow, clock, fill_ids = dependencies()
    uow.paper_orders.stale = True

    with pytest.raises(PaperOrderConcurrencyError):
        service.execute_next(ORDER_ID)

    assert clock.calls == fill_ids.calls == 1
    assert len(uow.paper_fills.add_calls) == 1
    assert len(uow.paper_orders.transition_calls) == 1
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_source_objects_remain_unchanged_after_success() -> None:
    source_intent = intent()
    source_snapshot = snapshot()
    service, uow, _, _ = dependencies(
        stored_intent=source_intent,
        stored_snapshot=source_snapshot,
    )

    service.execute_next(ORDER_ID)

    assert uow.trade_intents.value == source_intent
    assert uow.market_snapshots.value == source_snapshot
