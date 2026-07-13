"""Canonical test-row builders with no production persistence behavior."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    equity_snapshots,
    filter_evaluations,
    market_snapshots,
    paper_fills,
    paper_orders,
    paper_positions,
    position_events,
    strategy_decisions,
    trade_intents,
    trading_events,
)


def insert_canonical_graph(
    connection: Connection,
    *,
    decimal_value: Decimal = Decimal("123.123456789012345678"),
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Insert one valid row per table for constraint and round-trip tests."""

    now = observed_at or datetime.now(UTC)
    ids = _new_ids()
    connection.execute(
        market_snapshots.insert(),
        {
            "market_snapshot_id": ids["market_snapshot_id"],
            "symbol": "AAPL",
            "session_date": now.date(),
            "observed_at": now,
            "source": f"source-{ids['suffix']}",
            "open_price": decimal_value,
            "high_price": decimal_value + Decimal("2"),
            "low_price": decimal_value - Decimal("2"),
            "last_price": decimal_value + Decimal("1"),
            "previous_high_price": decimal_value + Decimal("3"),
            "previous_low_price": decimal_value - Decimal("3"),
            "previous_close_price": decimal_value,
            "volume": 100,
        },
    )
    connection.execute(
        candidates.insert(),
        {
            "candidate_id": ids["candidate_id"],
            "run_id": ids["run_id"],
            "market_snapshot_id": ids["market_snapshot_id"],
            "candidate_source": "RANKING",
            "rank": 1,
            "source_score": decimal_value,
            "selected_at": now,
        },
    )
    connection.execute(
        filter_evaluations.insert(),
        {
            "filter_evaluation_id": ids["filter_evaluation_id"],
            "candidate_id": ids["candidate_id"],
            "filter_set_id": ids["filter_set_id"],
            "evaluation_version": "v1",
            "passed": True,
            "score": decimal_value,
            "details": json.dumps({"observed": str(decimal_value)}, ensure_ascii=False),
            "evaluated_at": now,
        },
    )
    connection.execute(
        paper_positions.insert(),
        {
            "position_id": ids["position_id"],
            "strategy_id": ids["strategy_id"],
            "symbol": "AAPL",
            "currency": "USD",
            "status": "OPEN",
            "quantity": 10,
            "average_cost_price": decimal_value,
            "realized_pnl_amount": -decimal_value,
            "opened_at": now,
            "version": 1,
            "updated_at": now,
        },
    )
    connection.execute(
        strategy_decisions.insert(),
        {
            "decision_id": ids["decision_id"],
            "decision_key": f"decision-{ids['suffix']}",
            "candidate_id": ids["candidate_id"],
            "filter_evaluation_id": ids["filter_evaluation_id"],
            "strategy_id": ids["strategy_id"],
            "strategy_version": "v1",
            "action": "ENTER_LONG",
            "reason_codes": json.dumps(["PASS"]),
            "decided_at": now,
        },
    )
    connection.execute(
        trade_intents.insert(),
        {
            "trade_intent_id": ids["trade_intent_id"],
            "decision_id": ids["decision_id"],
            "idempotency_key": f"intent-{ids['suffix']}",
            "symbol": "AAPL",
            "currency": "USD",
            "side": "BUY",
            "order_type": "LIMIT",
            "requested_quantity": 10,
            "limit_price": decimal_value,
            "time_in_force": "DAY",
            "created_at": now,
        },
    )
    connection.execute(
        paper_orders.insert(),
        {
            "order_id": ids["order_id"],
            "trade_intent_id": ids["trade_intent_id"],
            "client_order_id": ids["client_order_id"],
            "broker_code": "PAPER",
            "broker_order_ref": f"broker-{ids['suffix']}",
            "status": "FILLED",
            "submitted_at": now,
            "accepted_at": now,
            "closed_at": now,
            "version": 1,
            "updated_at": now,
        },
    )
    connection.execute(
        paper_fills.insert(),
        {
            "fill_id": ids["fill_id"],
            "order_id": ids["order_id"],
            "execution_key": f"execution-{ids['suffix']}",
            "fill_sequence": 1,
            "quantity": 10,
            "price": decimal_value,
            "fee_amount": Decimal("0.010000000000000000"),
            "fee_currency": "USD",
            "executed_at": now,
        },
    )
    _insert_position_event_equity_and_event(connection, ids, now, decimal_value)
    return ids


def _insert_position_event_equity_and_event(
    connection: Connection, ids: dict[str, Any], now: datetime, value: Decimal
) -> None:
    connection.execute(
        position_events.insert(),
        {
            "position_event_id": ids["position_event_id"],
            "position_id": ids["position_id"],
            "fill_id": ids["fill_id"],
            "sequence_no": 1,
            "event_type": "OPENED",
            "quantity_delta": 10,
            "quantity_after": 10,
            "average_cost_after": value,
            "realized_pnl_delta": -value,
            "realized_pnl_after": -value,
            "occurred_at": now,
        },
    )
    connection.execute(
        equity_snapshots.insert(),
        {
            "equity_snapshot_id": ids["equity_snapshot_id"],
            "snapshot_key": f"equity-{ids['suffix']}",
            "strategy_id": ids["strategy_id"],
            "currency": "USD",
            "cash_amount": value,
            "market_value_amount": value,
            "equity_amount": value * 2,
            "realized_pnl_amount": -value,
            "unrealized_pnl_amount": value,
            "as_of": now,
        },
    )
    connection.execute(
        trading_events.insert(),
        {
            "event_id": ids["event_id"],
            "dedup_key": f"event-{ids['suffix']}",
            "event_type": "FILL_RECORDED",
            "stage": "PERSISTENCE_TEST",
            "severity": "INFO",
            "occurred_at": now,
            "correlation_id": uuid4(),
            "run_id": ids["run_id"],
            "strategy_id": ids["strategy_id"],
            "symbol": "AAPL",
            "market_snapshot_id": ids["market_snapshot_id"],
            "candidate_id": ids["candidate_id"],
            "filter_evaluation_id": ids["filter_evaluation_id"],
            "decision_id": ids["decision_id"],
            "trade_intent_id": ids["trade_intent_id"],
            "order_id": ids["order_id"],
            "fill_id": ids["fill_id"],
            "position_id": ids["position_id"],
            "equity_snapshot_id": ids["equity_snapshot_id"],
            "payload": json.dumps(
                {"message": "한글 보존", "decimal": str(value)}, ensure_ascii=False
            ),
        },
    )


def _new_ids() -> dict[str, UUID | str]:
    names = (
        "market_snapshot_id",
        "candidate_id",
        "run_id",
        "filter_evaluation_id",
        "filter_set_id",
        "position_id",
        "strategy_id",
        "decision_id",
        "trade_intent_id",
        "order_id",
        "client_order_id",
        "fill_id",
        "position_event_id",
        "equity_snapshot_id",
        "event_id",
    )
    values: dict[str, UUID | str] = {name: uuid4() for name in names}
    values["suffix"] = uuid4().hex
    return values
