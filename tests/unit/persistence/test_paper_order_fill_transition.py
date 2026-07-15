from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.repositories.paper_orders import (
    SqlAlchemyPaperOrderRepository,
)
from auto_trading_v2.application.contracts.paper_fills import PaperOrderFillTransition
from auto_trading_v2.application.errors import (
    OptimisticConcurrencyError,
    PersistenceNotFoundError,
)
from auto_trading_v2.domain.paper_orders import PaperOrderStatus
from auto_trading_v2.domain.primitives import OrderID

NOW = datetime(2026, 7, 15, 3, tzinfo=UTC)
ORDER_ID = OrderID(UUID(int=1))


def row(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "order_id": ORDER_ID.value,
        "trade_intent_id": UUID(int=2),
        "client_order_id": UUID(int=3),
        "broker_code": "INTERNAL_PAPER",
        "broker_order_ref": "internal-paper:v1:stable",
        "status": "PARTIALLY_FILLED",
        "rejection_code": None,
        "submitted_at": NOW,
        "accepted_at": NOW,
        "closed_at": None,
        "version": 2,
        "recorded_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return values


def transition(**changes: object) -> PaperOrderFillTransition:
    values: dict[str, object] = {
        "order_id": ORDER_ID,
        "expected_status": PaperOrderStatus.ACCEPTED,
        "expected_version": 1,
        "new_status": PaperOrderStatus.PARTIALLY_FILLED,
        "closed_at": None,
        "updated_at": NOW,
    }
    values.update(changes)
    return PaperOrderFillTransition(**values)  # type: ignore[arg-type]


def repository_for(*results: MagicMock) -> tuple[SqlAlchemyPaperOrderRepository, MagicMock]:
    connection = MagicMock()
    connection.execute.side_effect = results
    return SqlAlchemyPaperOrderRepository(cast(Connection, connection)), connection


def selected(value: dict[str, object] | None) -> MagicMock:
    result = MagicMock()
    result.mappings.return_value.one_or_none.return_value = value
    return result


def test_transition_guards_status_and_version_and_updates_only_fill_state() -> None:
    update_result = MagicMock(rowcount=1)
    repo, connection = repository_for(update_result, selected(row()))

    stored = repo.transition_after_fill(transition())

    statement = connection.execute.call_args_list[0].args[0]
    rendered = str(statement)
    params = statement.compile().params
    assert "paper_orders.order_id" in rendered
    assert "paper_orders.status" in rendered
    assert "paper_orders.version" in rendered
    assert {"status", "closed_at", "updated_at", "version"} == {
        str(key) for key in statement._values
    }
    assert "PARTIALLY_FILLED" in params.values()
    assert "ACCEPTED" in params.values()
    assert 1 in params.values() and 2 in params.values()
    assert stored.version == 2
    assert stored.accepted_at == stored.submitted_at == NOW
    assert stored.broker_code == "INTERNAL_PAPER"
    assert stored.broker_order_ref == "internal-paper:v1:stable"
    assert stored.rejection_code is None


def test_filled_transition_sets_closed_at_equal_to_updated_at() -> None:
    update_result = MagicMock(rowcount=1)
    final_row = row(status="FILLED", version=3, closed_at=NOW)
    repo, _ = repository_for(update_result, selected(final_row))

    stored = repo.transition_after_fill(
        transition(
            expected_status=PaperOrderStatus.PARTIALLY_FILLED,
            expected_version=2,
            new_status=PaperOrderStatus.FILLED,
            closed_at=NOW,
        )
    )

    assert stored.status is PaperOrderStatus.FILLED
    assert stored.version == 3
    assert stored.closed_at == stored.updated_at == NOW


def test_zero_row_with_existing_order_is_stale_without_retry() -> None:
    repo, connection = repository_for(MagicMock(rowcount=0), selected(row()))

    with pytest.raises(OptimisticConcurrencyError, match="stale_status_or_version"):
        repo.transition_after_fill(transition())

    assert connection.execute.call_count == 2


def test_zero_row_without_order_is_safe_not_found() -> None:
    repo, connection = repository_for(MagicMock(rowcount=0), selected(None))

    with pytest.raises(PersistenceNotFoundError, match="not_found"):
        repo.transition_after_fill(transition())

    assert connection.execute.call_count == 2
