from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, inspect, select, text
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import recommendations
from auto_trading_v2.domain.recommendations import RecommendationDisposition
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.recommendations.helpers import (
    command,
    persist_snapshot,
    row_for,
)

pytestmark = pytest.mark.integration


def test_live_recommendation_catalog_matches_metadata(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    inspector = inspect(mssql_database.engine)
    columns = inspector.get_columns("recommendations", schema="trading")
    assert tuple(column["name"] for column in columns) == tuple(recommendations.c.keys())
    assert len(columns) == 25
    assert inspector.get_pk_constraint("recommendations", schema="trading")[
        "constrained_columns"
    ] == ["recommendation_id"]
    foreign_keys = inspector.get_foreign_keys("recommendations", schema="trading")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_table"] == "feature_snapshots"
    with mssql_database.engine.connect() as connection:
        delete_action = connection.execute(
            text("SELECT delete_referential_action_desc FROM sys.foreign_keys WHERE name = :name"),
            {"name": "fk_recommendations_feature_snapshot_id_feature_snapshots"},
        ).scalar_one()
    assert delete_action == "NO_ACTION"
    reflected_indexes = {
        index["name"] for index in inspector.get_indexes("recommendations", schema="trading")
    }
    expected_indexes = {index.name for index in recommendations.indexes}
    expected_indexes.update(
        constraint.name
        for constraint in recommendations.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )
    assert reflected_indexes == expected_indexes
    with mssql_database.engine.connect() as connection:
        check_names = {
            str(row[0])
            for row in connection.execute(
                text(
                    "SELECT cc.name FROM sys.check_constraints cc "
                    "JOIN sys.tables t ON cc.parent_object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "WHERE s.name = 'trading' AND t.name = 'recommendations'"
                )
            )
        }
    assert check_names == {
        constraint.name
        for constraint in recommendations.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        constraint.name
        for constraint in recommendations.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    } == {"fk_recommendations_feature_snapshot_id_feature_snapshots"}


def _invalid_cases(
    valid: dict[str, object],
    market_risk: dict[str, object],
) -> list[dict[str, object]]:
    cases = []
    changes = (
        {"disposition": "UNKNOWN"},
        {"currency": None},
        {"entry_price_low": valid["stop_price"]},
        {"expected_holding_trading_days": 0},
        {"expected_holding_trading_days": 6},
        {"upside_probability": 2},
        {"target_probability": 0.9, "stop_probability": 0.2},
        {"expected_value_rate": -1},
        {"confidence": 2},
        {"reason_codes": "not-json"},
        {"reason_codes": "[]"},
        {"risk_codes": "[]"},
        {"invalidation_codes": "[]"},
        {"recommendation_key": "invalid"},
        {"content_digest": "g" * 64},
    )
    for change in changes:
        cases.append({**valid, **change, "recommendation_id": uuid4()})
    cases.append(
        {
            **valid,
            "recommendation_id": uuid4(),
            "disposition": "WATCH",
        }
    )
    cases.append({**market_risk, "recommendation_id": uuid4(), "risk_codes": "[]"})
    return cases


def test_representative_invalid_inserts_rollback_without_residue(
    mssql_database: TemporaryMssqlDatabase,
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    snapshot = persist_snapshot(sqlalchemy_uow_factory, 131)
    valid = row_for(command(snapshot, 131), snapshot, 131)
    market_risk_source = command(
        snapshot,
        132,
        disposition=RecommendationDisposition.MARKET_RISK,
        reason_codes=("MARKET_RISK_ACTIVE",),
    )
    market_risk = row_for(market_risk_source, snapshot, 132)

    for row in _invalid_cases(valid, market_risk):
        identifier = row["recommendation_id"]
        with mssql_database.engine.connect() as connection:
            transaction = connection.begin()
            with pytest.raises(IntegrityError):
                connection.execute(recommendations.insert().values(**row))
            transaction.rollback()
        with mssql_database.engine.connect() as connection:
            residue = connection.execute(
                select(recommendations.c.recommendation_id).where(
                    recommendations.c.recommendation_id == identifier
                )
            ).first()
        assert residue is None
