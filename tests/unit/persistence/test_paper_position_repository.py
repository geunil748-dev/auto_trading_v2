from datetime import UTC, datetime
from decimal import Decimal
from inspect import getmembers, isfunction
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.repositories.paper_positions import (
    SqlAlchemyPaperPositionRepository,
    map_paper_position,
)
from auto_trading_v2.application.contracts.position_projection import (
    PaperPositionBuyTransition,
)
from auto_trading_v2.application.errors import (
    OptimisticConcurrencyError,
    PersistenceMappingError,
    PersistenceNotFoundError,
)
from auto_trading_v2.application.ports.position_projection import PaperPositionRepository
from auto_trading_v2.domain.position_projection import PaperPositionStatus
from auto_trading_v2.domain.primitives import PositionID

NOW = datetime(2026, 7, 16, 3, tzinfo=UTC)
POSITION_ID = PositionID(UUID(int=1))
SENTINEL = "SHOULD_NEVER_APPEAR_PR10_9f31c2"


def row(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "position_id": POSITION_ID.value,
        "strategy_id": uuid4(),
        "symbol": "AAPL",
        "currency": "USD",
        "status": "OPEN",
        "quantity": 10,
        "average_cost_price": Decimal("100.000000000000000000"),
        "realized_pnl_amount": Decimal("0E-18"),
        "opened_at": NOW,
        "closed_at": None,
        "version": 1,
        "recorded_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return values


def transition() -> PaperPositionBuyTransition:
    from auto_trading_v2.domain.primitives import Price, Quantity

    return PaperPositionBuyTransition(
        position_id=POSITION_ID,
        expected_version=1,
        quantity=Quantity(15),
        average_cost_price=Price(Decimal("110")),
        updated_at=NOW,
    )


def selected(value: dict[str, object] | None) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.one_or_none.return_value = value
    return result


def repository_for(*results: MagicMock) -> tuple[SqlAlchemyPaperPositionRepository, MagicMock]:
    connection = MagicMock()
    connection.execute.side_effect = results
    return SqlAlchemyPaperPositionRepository(cast(Connection, connection)), connection


def test_repository_protocol_has_only_projection_mutations_and_reads() -> None:
    methods = {
        name
        for name, value in getmembers(PaperPositionRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {"add", "get", "get_open_by_key", "transition_after_buy_fill"}
    assert not {"commit", "rollback", "update", "delete", "upsert"}.intersection(methods)


def test_open_position_row_maps_to_typed_contract() -> None:
    mapped = map_paper_position(row())

    assert mapped.position_id == POSITION_ID
    assert mapped.status is PaperPositionStatus.OPEN
    assert mapped.quantity.value == 10
    assert mapped.average_cost_price.value == Decimal("100.000000000000000000")
    assert mapped.realized_pnl.amount == Decimal("0E-18")
    assert mapped.realized_pnl.currency.code == "USD"


@pytest.mark.parametrize(
    "changes",
    [
        {"position_id": "invalid"},
        {"status": "UNKNOWN"},
        {"quantity": 0},
        {"average_cost_price": Decimal("0")},
        {"currency": "INVALID"},
        {"opened_at": datetime(2026, 7, 16, 3)},
        {"position_id": None, "symbol": SENTINEL},
    ],
)
def test_invalid_rows_are_safely_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(PersistenceMappingError) as captured:
        map_paper_position(row(**changes))

    assert SENTINEL not in str(captured.value)
    assert SENTINEL not in repr(captured.value)


def test_transition_guards_open_status_and_expected_version() -> None:
    update_result = MagicMock(rowcount=1)
    updated = row(quantity=15, average_cost_price=Decimal("110"), version=2)
    repository, connection = repository_for(update_result, selected(updated))

    stored = repository.transition_after_buy_fill(transition())

    statement = connection.execute.call_args_list[0].args[0]
    rendered = str(statement)
    params = statement.compile().params
    assert "paper_positions.position_id" in rendered
    assert "paper_positions.status" in rendered
    assert "paper_positions.version" in rendered
    assert {str(key) for key in statement._values} == {
        "quantity",
        "average_cost_price",
        "updated_at",
        "version",
    }
    assert "OPEN" in params.values()
    assert 1 in params.values() and 2 in params.values()
    assert stored.version == 2
    assert stored.opened_at == NOW
    assert stored.realized_pnl.amount == 0


def test_transition_zero_row_distinguishes_stale_and_missing() -> None:
    stale, stale_connection = repository_for(MagicMock(rowcount=0), selected(row()))
    missing, missing_connection = repository_for(MagicMock(rowcount=0), selected(None))

    with pytest.raises(OptimisticConcurrencyError):
        stale.transition_after_buy_fill(transition())
    with pytest.raises(PersistenceNotFoundError):
        missing.transition_after_buy_fill(transition())

    assert stale_connection.execute.call_count == 2
    assert missing_connection.execute.call_count == 2


def test_repository_has_no_transaction_or_generic_mutation_methods() -> None:
    names = set(dir(SqlAlchemyPaperPositionRepository))
    assert not {"commit", "rollback", "begin", "update", "delete", "upsert"}.intersection(names)
