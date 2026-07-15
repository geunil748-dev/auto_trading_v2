from datetime import UTC, datetime
from decimal import Decimal
from inspect import getmembers, isfunction
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.repositories.paper_fills import (
    SqlAlchemyPaperFillRepository,
    map_paper_fill,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.paper_fills import PaperFillRepository
from auto_trading_v2.domain.primitives import FillID, OrderID

SENTINEL = "SHOULD_NEVER_APPEAR_PR9_74a0e1"
NOW = datetime(2026, 7, 15, 3, tzinfo=UTC)


def row(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "fill_id": uuid4(),
        "order_id": uuid4(),
        "execution_key": "order:id|fill-policy:internal-paper-split-fill|version:v1|sequence:1",
        "fill_sequence": 1,
        "quantity": 20,
        "price": Decimal("25.125000000000000000"),
        "fee_amount": Decimal("0E-18"),
        "fee_currency": "USD",
        "executed_at": NOW,
        "recorded_at": NOW,
    }
    values.update(changes)
    return values


def test_repository_protocol_has_exact_immutable_fill_api() -> None:
    methods = {
        name
        for name, value in getmembers(PaperFillRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {
        "add",
        "get",
        "get_by_execution_key",
        "get_by_order_sequence",
        "list_by_order",
    }
    assert not {"commit", "rollback", "update", "delete", "upsert"}.intersection(methods)


def test_row_maps_to_typed_fill_contract() -> None:
    mapped = map_paper_fill(row())

    assert isinstance(mapped.fill_id, FillID)
    assert isinstance(mapped.order_id, OrderID)
    assert mapped.fill_sequence == 1
    assert mapped.quantity.value == 20
    assert mapped.price.value == Decimal("25.125000000000000000")
    assert mapped.fee.amount == Decimal("0E-18")
    assert mapped.fee.currency.code == "USD"
    assert mapped.executed_at == mapped.recorded_at == NOW


@pytest.mark.parametrize(
    "changes",
    [
        {"fill_id": "invalid"},
        {"fill_sequence": 0},
        {"quantity": 0},
        {"price": Decimal("0")},
        {"fee_amount": Decimal("-1")},
        {"fee_currency": "INVALID"},
        {"executed_at": datetime(2026, 7, 15, 3)},
        {"recorded_at": datetime(2026, 7, 15, 3)},
        {"fill_id": None, "execution_key": SENTINEL},
    ],
)
def test_invalid_rows_are_safely_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(PersistenceMappingError) as captured:
        map_paper_fill(row(**changes))

    assert SENTINEL not in str(captured.value)
    assert SENTINEL not in repr(captured.value)


def test_repository_owns_no_transaction_or_mutation_methods() -> None:
    names = set(dir(SqlAlchemyPaperFillRepository))
    assert not {
        "commit",
        "rollback",
        "begin",
        "update",
        "delete",
        "upsert",
        "transition_after_fill",
    }.intersection(names)
