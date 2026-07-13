from datetime import UTC, datetime, timedelta, timezone

import pytest

from auto_trading_v2.adapters.persistence.tables import market_snapshots

from .records import insert_canonical_graph

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "observed_at",
    [
        datetime(2026, 7, 13, 1, 2, 3, 456789, tzinfo=UTC),
        datetime(2026, 7, 13, 10, 2, 3, 456789, tzinfo=timezone(timedelta(hours=9))),
        datetime(2026, 7, 12, 20, 32, 3, 456789, tzinfo=timezone(timedelta(hours=-4, minutes=-30))),
    ],
)
def test_datetimeoffset_round_trip_preserves_utc_instant(
    mssql_database: object, observed_at: datetime
) -> None:
    with mssql_database.engine.begin() as connection:
        ids = insert_canonical_graph(connection, observed_at=observed_at)
        row = (
            connection.execute(
                market_snapshots.select().where(
                    market_snapshots.c.market_snapshot_id == ids["market_snapshot_id"]
                )
            )
            .mappings()
            .one()
        )

    returned = row["observed_at"]
    recorded = row["recorded_at"]
    assert returned.tzinfo is not None
    assert returned.astimezone(UTC) == observed_at.astimezone(UTC)
    assert recorded.tzinfo is not None
    assert recorded.utcoffset() == timedelta(0)
