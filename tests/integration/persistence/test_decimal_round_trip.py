from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from uuid import uuid4

import pytest
from sqlalchemy.exc import DataError, StatementError

from auto_trading_v2.adapters.persistence.tables import (
    equity_snapshots,
    filter_evaluations,
    market_snapshots,
    paper_fills,
    paper_positions,
)

from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("value", "pnl_value"),
    [
        (
            Decimal("12345678901234567890.123456789012345678"),
            Decimal("-999999999999999999.999999999999999999"),
        ),
        (
            Decimal("0.000000000000000001"),
            Decimal("-0.000000000000000001"),
        ),
    ],
    ids=["maximum-scale", "minimum-scale"],
)
def test_decimal_38_18_values_round_trip_without_float_conversion(
    mssql_database: object,
    value: Decimal,
    pnl_value: Decimal,
) -> None:
    with localcontext() as context:
        context.prec = 38
        expected_equity = value + value
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(
            connection,
            decimal_value=value,
            pnl_value=pnl_value,
        )
        observed = {
            "market": connection.execute(
                market_snapshots.select()
                .with_only_columns(market_snapshots.c.open_price)
                .where(market_snapshots.c.market_snapshot_id == ids["market_snapshot_id"])
            ).scalar_one(),
            "score": connection.execute(
                filter_evaluations.select()
                .with_only_columns(filter_evaluations.c.score)
                .where(filter_evaluations.c.filter_evaluation_id == ids["filter_evaluation_id"])
            ).scalar_one(),
            "fill": connection.execute(
                paper_fills.select()
                .with_only_columns(paper_fills.c.price)
                .where(paper_fills.c.fill_id == ids["fill_id"])
            ).scalar_one(),
            "pnl": connection.execute(
                paper_positions.select()
                .with_only_columns(paper_positions.c.realized_pnl_amount)
                .where(paper_positions.c.position_id == ids["position_id"])
            ).scalar_one(),
            "equity": connection.execute(
                equity_snapshots.select()
                .with_only_columns(equity_snapshots.c.equity_amount)
                .where(equity_snapshots.c.equity_snapshot_id == ids["equity_snapshot_id"])
            ).scalar_one(),
        }

    assert observed["market"] == value
    assert observed["score"] == value
    assert observed["fill"] == value
    assert observed["pnl"] == pnl_value
    assert observed["equity"] == expected_equity
    assert all(isinstance(item, Decimal) for item in observed.values())


def test_decimal_integer_precision_overflow_fails_explicitly(mssql_database: object) -> None:
    too_large = Decimal("123456789012345678901.123456789012345678")

    with (
        pytest.raises((DataError, StatementError, ArithmeticError)),
        mssql_database.engine.begin() as connection,
    ):
        connection.execute(
            market_snapshots.insert(),
            {
                "market_snapshot_id": uuid4(),
                "symbol": "AAPL",
                "session_date": date.today(),
                "observed_at": datetime.now(UTC),
                "source": uuid4().hex,
                "open_price": too_large,
                "high_price": too_large,
                "low_price": too_large,
                "last_price": too_large,
                "previous_high_price": too_large,
                "previous_low_price": too_large,
            },
        )
