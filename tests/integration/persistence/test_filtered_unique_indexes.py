from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.tables import paper_positions, strategy_decisions

from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


def test_second_open_position_for_same_strategy_symbol_currency_is_rejected(
    mssql_database: object,
) -> None:
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            paper_positions.insert(),
            {
                "position_id": uuid4(),
                "strategy_id": ids["strategy_id"],
                "symbol": "AAPL",
                "currency": "USD",
                "status": "OPEN",
                "quantity": 1,
                "average_cost_price": Decimal("1"),
                "realized_pnl_amount": Decimal("0"),
                "opened_at": datetime.now(UTC),
                "version": 1,
                "updated_at": datetime.now(UTC),
            },
        )


def test_closed_position_history_is_allowed_for_same_key(mssql_database: object) -> None:
    strategy_id = uuid4()
    now = datetime.now(UTC)
    values = [
        {
            "position_id": uuid4(),
            "strategy_id": strategy_id,
            "symbol": "MSFT",
            "currency": "USD",
            "status": "CLOSED",
            "quantity": 0,
            "average_cost_price": Decimal("0"),
            "realized_pnl_amount": Decimal("-1"),
            "opened_at": now,
            "closed_at": now,
            "version": 1,
            "updated_at": now,
        }
        for _ in range(2)
    ]

    with mssql_database.engine.begin() as connection:
        connection.execute(paper_positions.insert(), values)


def test_second_candidate_decision_for_same_strategy_version_is_rejected(
    mssql_database: object,
) -> None:
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection)

    with pytest.raises(IntegrityError), mssql_database.engine.begin() as connection:
        connection.execute(
            strategy_decisions.insert(),
            {
                "decision_id": uuid4(),
                "decision_key": uuid4().hex,
                "candidate_id": ids["candidate_id"],
                "filter_evaluation_id": ids["filter_evaluation_id"],
                "strategy_id": ids["strategy_id"],
                "strategy_version": "v1",
                "action": "SKIP",
                "reason_codes": "[]",
                "decided_at": datetime.now(UTC),
            },
        )
