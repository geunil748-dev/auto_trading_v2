from dataclasses import replace
from datetime import timedelta

import pytest

from auto_trading_v2.application.contracts.paper_orders import PaperOrderSubmissionResult
from auto_trading_v2.application.errors import (
    InvalidPaperBrokerResultError,
    PaperOrderConflictError,
    PaperOrderSubmissionError,
    TradeIntentNotFoundError,
)
from auto_trading_v2.application.services.paper_order import PaperOrderSubmissionService
from auto_trading_v2.domain.paper_orders import (
    PaperBrokerSubmissionOutcome,
    PaperOrderStatus,
)

from .paper_order_fakes import (
    NOW,
    TRADE_INTENT_ID,
    CountingClock,
    FakeBroker,
    FakeClientOrderIDFactory,
    FakeOrderIDFactory,
    FakeUnitOfWork,
    FakeUnitOfWorkFactory,
    broker_result,
    stored_order,
    stored_trade_intent,
)


def dependencies(
    intent_present: bool = True,
    *,
    broker: FakeBroker | None = None,
) -> tuple[
    PaperOrderSubmissionService,
    FakeUnitOfWork,
    CountingClock,
    FakeClientOrderIDFactory,
    FakeOrderIDFactory,
    FakeBroker,
]:
    unit_of_work = FakeUnitOfWork(stored_trade_intent() if intent_present else None)
    clock = CountingClock()
    client_factory = FakeClientOrderIDFactory()
    order_factory = FakeOrderIDFactory()
    selected_broker = broker or FakeBroker()
    service = PaperOrderSubmissionService(
        FakeUnitOfWorkFactory(unit_of_work),
        clock,
        order_factory,
        client_factory,
        selected_broker,
    )
    return service, unit_of_work, clock, client_factory, order_factory, selected_broker


def test_missing_trade_intent_has_no_downstream_effects() -> None:
    service, uow, clock, client_ids, order_ids, broker = dependencies(False)

    with pytest.raises(TradeIntentNotFoundError):
        service.submit(TRADE_INTENT_ID)

    assert uow.trade_intents.get_calls == 1
    assert client_ids.calls == order_ids.calls == clock.calls == 0
    assert broker.calls == []
    assert uow.paper_orders.add_calls == []
    assert uow.commit_calls == 0


def test_existing_trade_intent_order_conflicts_before_identity_or_broker() -> None:
    service, uow, clock, client_ids, order_ids, broker = dependencies()
    uow.paper_orders.by_trade_intent = stored_order()

    with pytest.raises(PaperOrderConflictError, match="trade_intent_exists"):
        service.submit(TRADE_INTENT_ID)

    assert client_ids.calls == order_ids.calls == clock.calls == 0
    assert broker.calls == []
    assert uow.paper_orders.add_calls == []
    assert uow.commit_calls == 0


def test_deterministic_client_order_conflict_precedes_clock_and_broker() -> None:
    service, uow, clock, client_ids, order_ids, broker = dependencies()
    uow.paper_orders.by_client = stored_order()

    with pytest.raises(PaperOrderConflictError, match="client_order_id_exists"):
        service.submit(TRADE_INTENT_ID)

    assert client_ids.calls == 1
    assert order_ids.calls == clock.calls == 0
    assert broker.calls == []
    assert uow.paper_orders.add_calls == []
    assert uow.commit_calls == 0


def test_accepted_result_is_stored_and_committed_once_without_source_mutation() -> None:
    service, uow, clock, client_ids, order_ids, broker = dependencies()
    source = uow.trade_intents.value

    stored = service.submit(TRADE_INTENT_ID)

    assert uow.trade_intents.value == source
    assert uow.trade_intents.get_calls == 1
    assert client_ids.calls == order_ids.calls == clock.calls == 1
    assert len(broker.calls) == len(uow.paper_orders.add_calls) == 1
    assert uow.commit_calls == 1
    assert stored.status is PaperOrderStatus.ACCEPTED
    assert stored.version == 1
    assert stored.accepted_at == NOW
    assert stored.closed_at is None
    assert stored.rejection_code is None


def test_rejected_result_is_a_committed_canonical_order() -> None:
    service, uow, clock, client_ids, order_ids, broker = dependencies(
        broker=FakeBroker(broker_result(PaperBrokerSubmissionOutcome.REJECTED))
    )

    stored = service.submit(TRADE_INTENT_ID)

    assert client_ids.calls == order_ids.calls == clock.calls == 1
    assert len(broker.calls) == len(uow.paper_orders.add_calls) == 1
    assert uow.commit_calls == 1
    assert stored.status is PaperOrderStatus.REJECTED
    assert stored.accepted_at is None
    assert stored.closed_at == NOW
    assert stored.rejection_code == "UNSUPPORTED_SIDE"


def test_technical_broker_failure_rolls_back_before_order_identity_or_write() -> None:
    service, uow, clock, client_ids, order_ids, broker = dependencies(broker=FakeBroker(fail=True))

    with pytest.raises(PaperOrderSubmissionError, match="adapter_unavailable"):
        service.submit(TRADE_INTENT_ID)

    assert client_ids.calls == clock.calls == len(broker.calls) == 1
    assert order_ids.calls == 0
    assert uow.paper_orders.add_calls == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


@pytest.mark.parametrize(
    "result",
    [
        object(),
        replace(broker_result(), broker_code="OTHER"),
        PaperOrderSubmissionResult(
            outcome=PaperBrokerSubmissionOutcome.ACCEPTED,
            broker_code="INTERNAL_PAPER",
            broker_order_ref="reference",
            processed_at=NOW - timedelta(seconds=1),
            rejection_code=None,
        ),
    ],
)
def test_invalid_broker_result_rolls_back_before_order_identity_or_write(
    result: object,
) -> None:
    service, uow, _, _, order_ids, _ = dependencies(broker=FakeBroker(result))

    with pytest.raises(InvalidPaperBrokerResultError):
        service.submit(TRADE_INTENT_ID)

    assert order_ids.calls == 0
    assert uow.paper_orders.add_calls == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_broker_reference_conflict_precedes_order_identity_and_write() -> None:
    service, uow, _, _, order_ids, broker = dependencies()
    uow.paper_orders.by_reference = stored_order()

    with pytest.raises(PaperOrderConflictError, match="broker_reference_exists"):
        service.submit(TRADE_INTENT_ID)

    assert len(broker.calls) == 1
    assert order_ids.calls == 0
    assert uow.paper_orders.add_calls == []
    assert uow.commit_calls == 0


def test_duplicate_add_race_rolls_back_without_retry_or_commit() -> None:
    service, uow, _, _, order_ids, broker = dependencies()
    uow.paper_orders.fail_duplicate = True

    with pytest.raises(PaperOrderConflictError, match="duplicate_record"):
        service.submit(TRADE_INTENT_ID)

    assert len(broker.calls) == 1
    assert order_ids.calls == 1
    assert len(uow.paper_orders.add_calls) == 1
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
