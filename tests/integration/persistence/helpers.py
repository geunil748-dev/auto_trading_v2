"""Small SQL helpers used only by the MSSQL integration suite."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, Table

from auto_trading_v2.adapters.persistence.tables import (
    paper_orders,
    strategy_decisions,
    trade_intents,
)


def clone_row(
    connection: Connection,
    table: Table,
    primary_key_name: str,
    primary_key_value: UUID,
    **changes: Any,
) -> dict[str, Any]:
    """Load one canonical row, remove its server default, and apply changes."""

    primary_key = table.c[primary_key_name]
    row = dict(
        connection.execute(table.select().where(primary_key == primary_key_value)).mappings().one()
    )
    row.pop("recorded_at", None)
    row.update(changes)
    return row


def insert_decision(connection: Connection, ids: dict[str, Any], *, suffix: str) -> UUID:
    """Insert an additional position-based decision with a unique semantic key."""

    decision_id = uuid4()
    connection.execute(
        strategy_decisions.insert(),
        {
            "decision_id": decision_id,
            "decision_key": f"decision-{suffix}",
            "position_id": ids["position_id"],
            "market_snapshot_id": ids["market_snapshot_id"],
            "strategy_id": ids["strategy_id"],
            "strategy_version": f"test-{suffix}",
            "action": "EXIT_LONG",
            "reason_codes": json.dumps(["TEST"]),
            "decided_at": datetime.now(UTC),
        },
    )
    return decision_id


def insert_intent(
    connection: Connection,
    decision_id: UUID,
    *,
    suffix: str,
    idempotency_key: str | None = None,
) -> UUID:
    """Insert an additional valid market trade intent."""

    trade_intent_id = uuid4()
    connection.execute(
        trade_intents.insert(),
        {
            "trade_intent_id": trade_intent_id,
            "decision_id": decision_id,
            "idempotency_key": idempotency_key or f"intent-{suffix}",
            "symbol": "AAPL",
            "currency": "USD",
            "side": "SELL",
            "order_type": "MARKET",
            "requested_quantity": 1,
            "time_in_force": "DAY",
            "created_at": datetime.now(UTC),
        },
    )
    return trade_intent_id


def insert_order(
    connection: Connection,
    trade_intent_id: UUID,
    *,
    suffix: str,
    client_order_id: UUID | None = None,
    broker_order_ref: str | None = None,
) -> UUID:
    """Insert an additional valid active paper order."""

    now = datetime.now(UTC)
    order_id = uuid4()
    connection.execute(
        paper_orders.insert(),
        {
            "order_id": order_id,
            "trade_intent_id": trade_intent_id,
            "client_order_id": client_order_id or uuid4(),
            "broker_code": "PAPER",
            "broker_order_ref": broker_order_ref,
            "status": "CREATED",
            "submitted_at": now,
            "version": 1,
            "updated_at": now,
        },
    )
    return order_id


def insert_decision_intent_order(
    connection: Connection,
    ids: dict[str, Any],
    *,
    suffix: str,
    broker_order_ref: str | None = None,
) -> tuple[UUID, UUID, UUID]:
    """Insert a valid independent decision, intent, and paper order chain."""

    decision_id = insert_decision(connection, ids, suffix=suffix)
    intent_id = insert_intent(connection, decision_id, suffix=suffix)
    order_id = insert_order(
        connection,
        intent_id,
        suffix=suffix,
        broker_order_ref=broker_order_ref,
    )
    return decision_id, intent_id, order_id
