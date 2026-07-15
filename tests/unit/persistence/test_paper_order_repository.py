from datetime import UTC, datetime
from inspect import getmembers, isfunction
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.repositories.paper_orders import (
    SqlAlchemyPaperOrderRepository,
    map_paper_order,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.paper_orders import PaperOrderRepository
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import ClientOrderID, OrderID, TradeIntentID

SENTINEL = "SHOULD_NEVER_APPEAR_PR8_6c19e2"
NOW = datetime(2026, 7, 15, 1, tzinfo=UTC)


def row(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "order_id": uuid4(),
        "trade_intent_id": uuid4(),
        "client_order_id": uuid4(),
        "broker_code": "INTERNAL_PAPER",
        "broker_order_ref": "internal-paper:v1:reference",
        "status": "ACCEPTED",
        "rejection_code": None,
        "submitted_at": NOW,
        "accepted_at": NOW,
        "closed_at": None,
        "version": 1,
        "recorded_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return values


def test_repository_protocol_has_only_required_add_and_reads() -> None:
    methods = {
        name
        for name, value in getmembers(PaperOrderRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {
        "add",
        "get",
        "get_by_trade_intent",
        "get_by_client_order_id",
        "get_by_broker_reference",
    }
    assert not {"commit", "rollback", "update", "delete", "upsert"}.intersection(methods)


def test_accepted_and_rejected_rows_map_to_typed_contracts() -> None:
    accepted = map_paper_order(row())
    rejected = map_paper_order(
        row(
            status="REJECTED",
            accepted_at=None,
            closed_at=NOW,
            rejection_code="UNSUPPORTED_SIDE",
        )
    )

    assert isinstance(accepted.order_id, OrderID)
    assert isinstance(accepted.trade_intent_id, TradeIntentID)
    assert isinstance(accepted.client_order_id, ClientOrderID)
    assert accepted.status is PaperOrderStatus.ACCEPTED
    assert accepted.closed_at is None
    assert rejected.status is PaperOrderStatus.REJECTED
    assert rejected.accepted_at is None
    assert rejected.closed_at == NOW
    assert rejected.rejection_code == "UNSUPPORTED_SIDE"


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "UNKNOWN"},
        {"version": 0},
        {"submitted_at": datetime(2026, 7, 15)},
        {"status": "ACCEPTED", "accepted_at": None},
        {"status": "REJECTED", "accepted_at": None, "closed_at": NOW, "rejection_code": None},
        {"order_id": None, "broker_order_ref": SENTINEL},
    ],
)
def test_invalid_rows_are_safely_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(PersistenceMappingError) as captured:
        map_paper_order(row(**changes))

    assert SENTINEL not in str(captured.value)
    assert SENTINEL not in repr(captured.value)


def test_repository_owns_no_transaction_or_mutation_methods() -> None:
    names = set(dir(SqlAlchemyPaperOrderRepository))
    assert not {"commit", "rollback", "begin", "update", "delete", "upsert"}.intersection(names)
