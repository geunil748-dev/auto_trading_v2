import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    equity_snapshots,
    filter_evaluations,
    market_snapshots,
    strategy_decisions,
    trading_events,
)

from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


def test_market_snapshot_semantic_duplicate_is_rejected(mssql_database: object) -> None:
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        existing = dict(
            connection.execute(
                market_snapshots.select().where(
                    market_snapshots.c.market_snapshot_id == ids["market_snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
        existing.pop("recorded_at")
        existing["market_snapshot_id"] = uuid4()

        with pytest.raises(IntegrityError):
            connection.execute(market_snapshots.insert(), existing)


def test_referential_integrity_rejects_missing_snapshot(mssql_database: object) -> None:
    now = datetime.now(UTC)
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            candidates.insert(),
            {
                "candidate_id": uuid4(),
                "run_id": uuid4(),
                "market_snapshot_id": uuid4(),
                "candidate_source": "RANKING",
                "rank": 1,
                "selected_at": now,
            },
        )


@pytest.mark.parametrize("symbol", ["bad symbol", "A/B", "lower"])
def test_invalid_symbol_is_rejected_by_database(mssql_database: object, symbol: str) -> None:
    now = datetime.now(UTC)
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            market_snapshots.insert(),
            {
                "market_snapshot_id": uuid4(),
                "symbol": symbol,
                "session_date": now.date(),
                "observed_at": now,
                "source": uuid4().hex,
                "open_price": Decimal("1"),
                "high_price": Decimal("2"),
                "low_price": Decimal("1"),
                "last_price": Decimal("1"),
                "previous_high_price": Decimal("2"),
                "previous_low_price": Decimal("1"),
            },
        )


def test_json_shape_constraints_reject_wrong_top_level_values(mssql_database: object) -> None:
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            filter_evaluations.insert(),
            {
                "filter_evaluation_id": uuid4(),
                "candidate_id": ids["candidate_id"],
                "filter_set_id": uuid4(),
                "evaluation_version": "wrong-shape",
                "passed": False,
                "details": json.dumps(["array-not-object"]),
                "evaluated_at": datetime.now(UTC),
            },
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            trading_events.insert(),
            {
                "event_id": uuid4(),
                "dedup_key": uuid4().hex,
                "event_type": "TEST",
                "stage": "TEST",
                "severity": "INFO",
                "occurred_at": datetime.now(UTC),
                "payload": json.dumps(["array-not-object"]),
            },
        )

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            strategy_decisions.insert(),
            {
                "decision_id": uuid4(),
                "decision_key": uuid4().hex,
                "position_id": ids["position_id"],
                "position_version": 1,
                "market_snapshot_id": ids["market_snapshot_id"],
                "strategy_id": ids["strategy_id"],
                "strategy_version": "wrong-shape",
                "action": "OBSERVE",
                "reason_codes": json.dumps({"not": "an-array"}),
                "decided_at": datetime.now(UTC),
            },
        )


def test_invalid_json_is_rejected_and_unicode_decimal_strings_round_trip(
    mssql_database: object,
) -> None:
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        details = connection.execute(
            filter_evaluations.select()
            .with_only_columns(filter_evaluations.c.details)
            .where(filter_evaluations.c.filter_evaluation_id == ids["filter_evaluation_id"])
        ).scalar_one()
        payload = connection.execute(
            trading_events.select()
            .with_only_columns(trading_events.c.payload)
            .where(trading_events.c.event_id == ids["event_id"])
        ).scalar_one()
        reasons = connection.execute(
            strategy_decisions.select()
            .with_only_columns(strategy_decisions.c.reason_codes)
            .where(strategy_decisions.c.decision_id == ids["decision_id"])
        ).scalar_one()

    assert json.loads(details)["observed"] == "123.123456789012345678"
    assert json.loads(payload)["message"] == "한글 보존"
    assert json.loads(payload)["decimal"] == "123.123456789012345678"
    assert json.loads(reasons) == ["PASS"]

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            filter_evaluations.insert(),
            {
                "filter_evaluation_id": uuid4(),
                "candidate_id": ids["candidate_id"],
                "filter_set_id": uuid4(),
                "evaluation_version": "invalid-json",
                "passed": False,
                "details": "{invalid-json",
                "evaluated_at": datetime.now(UTC),
            },
        )


@pytest.mark.parametrize(
    ("table", "primary_key", "id_key", "json_column", "invalid_value"),
    [
        (filter_evaluations, "filter_evaluation_id", "filter_evaluation_id", "details", "[]"),
        (
            filter_evaluations,
            "filter_evaluation_id",
            "filter_evaluation_id",
            "details",
            "{invalid",
        ),
        (
            filter_evaluations,
            "filter_evaluation_id",
            "filter_evaluation_id",
            "details",
            "plain text",
        ),
        (filter_evaluations, "filter_evaluation_id", "filter_evaluation_id", "details", None),
        (strategy_decisions, "decision_id", "decision_id", "reason_codes", "{}"),
        (strategy_decisions, "decision_id", "decision_id", "reason_codes", "[invalid"),
        (strategy_decisions, "decision_id", "decision_id", "reason_codes", "plain text"),
        (strategy_decisions, "decision_id", "decision_id", "reason_codes", None),
        (trading_events, "event_id", "event_id", "payload", "[]"),
        (trading_events, "event_id", "event_id", "payload", "{invalid"),
        (trading_events, "event_id", "event_id", "payload", "plain text"),
        (trading_events, "event_id", "event_id", "payload", None),
    ],
)
def test_json_columns_reject_invalid_shape_text_and_null(
    mssql_database: object,
    table: object,
    primary_key: str,
    id_key: str,
    json_column: str,
    invalid_value: str | None,
) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)
        connection.execute(
            table.update()
            .where(table.c[primary_key] == ids[id_key])
            .values(**{json_column: invalid_value})
        )


def test_equity_formula_constraint_rejects_mismatch(mssql_database: object) -> None:
    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            equity_snapshots.insert(),
            {
                "equity_snapshot_id": uuid4(),
                "snapshot_key": uuid4().hex,
                "strategy_id": uuid4(),
                "currency": "USD",
                "cash_amount": Decimal("10"),
                "market_value_amount": Decimal("5"),
                "equity_amount": Decimal("99"),
                "realized_pnl_amount": Decimal("0"),
                "unrealized_pnl_amount": Decimal("0"),
                "as_of": datetime.now(UTC),
            },
        )
