from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    equity_snapshots,
    market_snapshots,
    paper_fills,
    paper_orders,
    paper_positions,
    position_events,
    trade_intents,
    trading_events,
)

from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


def _invalid_change(case: str) -> tuple[object, str, str, dict[str, object]]:
    now = datetime.now(UTC)
    cases = {
        "price_zero": (
            market_snapshots,
            "market_snapshot_id",
            "market_snapshot_id",
            {"open_price": 0},
        ),
        "previous_close_zero": (
            market_snapshots,
            "market_snapshot_id",
            "market_snapshot_id",
            {"previous_close_price": 0},
        ),
        "volume_negative": (
            market_snapshots,
            "market_snapshot_id",
            "market_snapshot_id",
            {"volume": -1},
        ),
        "high_below_low": (
            market_snapshots,
            "market_snapshot_id",
            "market_snapshot_id",
            {"high_price": Decimal("1"), "low_price": Decimal("2")},
        ),
        "previous_high_below_low": (
            market_snapshots,
            "market_snapshot_id",
            "market_snapshot_id",
            {"previous_high_price": Decimal("1"), "previous_low_price": Decimal("2")},
        ),
        "rank_zero": (candidates, "candidate_id", "candidate_id", {"rank": 0}),
        "currency_lowercase": (
            trade_intents,
            "trade_intent_id",
            "trade_intent_id",
            {"currency": "usd"},
        ),
        "symbol_invalid": (
            trade_intents,
            "trade_intent_id",
            "trade_intent_id",
            {"symbol": "A/B"},
        ),
        "position_quantity_negative": (
            paper_positions,
            "position_id",
            "position_id",
            {"quantity": -1},
        ),
        "requested_quantity_zero": (
            trade_intents,
            "trade_intent_id",
            "trade_intent_id",
            {"requested_quantity": 0},
        ),
        "limit_without_price": (
            trade_intents,
            "trade_intent_id",
            "trade_intent_id",
            {"order_type": "LIMIT", "limit_price": None},
        ),
        "market_with_price": (
            trade_intents,
            "trade_intent_id",
            "trade_intent_id",
            {"order_type": "MARKET", "limit_price": Decimal("1")},
        ),
        "fill_quantity_zero": (paper_fills, "fill_id", "fill_id", {"quantity": 0}),
        "fill_sequence_zero": (
            paper_fills,
            "fill_id",
            "fill_id",
            {"fill_sequence": 0},
        ),
        "fill_price_zero": (paper_fills, "fill_id", "fill_id", {"price": 0}),
        "fee_negative": (
            paper_fills,
            "fill_id",
            "fill_id",
            {"fee_amount": Decimal("-1")},
        ),
        "fill_currency_invalid": (
            paper_fills,
            "fill_id",
            "fill_id",
            {"fee_currency": "usd"},
        ),
        "open_quantity_zero": (
            paper_positions,
            "position_id",
            "position_id",
            {"quantity": 0},
        ),
        "open_with_closed_at": (
            paper_positions,
            "position_id",
            "position_id",
            {"closed_at": now},
        ),
        "closed_with_quantity": (
            paper_positions,
            "position_id",
            "position_id",
            {"status": "CLOSED", "quantity": 1, "closed_at": now},
        ),
        "closed_without_time": (
            paper_positions,
            "position_id",
            "position_id",
            {"status": "CLOSED", "quantity": 0, "closed_at": None},
        ),
        "invalid_order_status": (
            paper_orders,
            "order_id",
            "order_id",
            {"status": "UNKNOWN"},
        ),
        "active_order_closed": (
            paper_orders,
            "order_id",
            "order_id",
            {"status": "ACCEPTED"},
        ),
        "terminal_order_without_close": (
            paper_orders,
            "order_id",
            "order_id",
            {"closed_at": None},
        ),
        "position_delta_zero": (
            position_events,
            "position_event_id",
            "position_event_id",
            {"quantity_delta": 0},
        ),
        "equity_formula": (
            equity_snapshots,
            "equity_snapshot_id",
            "equity_snapshot_id",
            {"equity_amount": Decimal("999")},
        ),
        "event_severity": (
            trading_events,
            "event_id",
            "event_id",
            {"severity": "UNKNOWN"},
        ),
        "event_stage_empty": (
            trading_events,
            "event_id",
            "event_id",
            {"stage": "   "},
        ),
    }
    return cases[case]


@pytest.mark.parametrize(
    "case",
    [
        "price_zero",
        "previous_close_zero",
        "volume_negative",
        "high_below_low",
        "previous_high_below_low",
        "rank_zero",
        "currency_lowercase",
        "symbol_invalid",
        "position_quantity_negative",
        "requested_quantity_zero",
        "limit_without_price",
        "market_with_price",
        "fill_quantity_zero",
        "fill_sequence_zero",
        "fill_price_zero",
        "fee_negative",
        "fill_currency_invalid",
        "open_quantity_zero",
        "open_with_closed_at",
        "closed_with_quantity",
        "closed_without_time",
        "invalid_order_status",
        "active_order_closed",
        "terminal_order_without_close",
        "position_delta_zero",
        "equity_formula",
        "event_severity",
        "event_stage_empty",
    ],
)
def test_invalid_business_state_is_rejected_by_check_constraint(
    mssql_database: object, case: str
) -> None:
    table, primary_key_name, id_key, changes = _invalid_change(case)
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            table.update().where(table.c[primary_key_name] == ids[id_key]).values(**changes)
        )
