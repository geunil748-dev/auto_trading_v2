"""Real MSSQL Unit of Work rollback and atomicity tests."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select

from auto_trading_v2.adapters.persistence.tables import market_snapshots
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import DuplicateRecordError, ForeignKeyViolationError
from auto_trading_v2.domain.primitives import MarketSnapshotID
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.persistence.repository_records import (
    new_candidate,
    new_evaluation,
    new_snapshot,
)

pytestmark = pytest.mark.integration


def _snapshot_exists(
    mssql_database: TemporaryMssqlDatabase,
    snapshot_id: MarketSnapshotID,
) -> bool:
    with mssql_database.engine.connect() as connection:
        return (
            connection.execute(
                select(market_snapshots.c.market_snapshot_id).where(
                    market_snapshots.c.market_snapshot_id == snapshot_id.value
                )
            ).one_or_none()
            is not None
        )


def test_normal_exit_without_commit_rolls_back(mssql_database: TemporaryMssqlDatabase) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()

    with factory() as uow:
        uow.market_snapshots.add(snapshot)

    assert not _snapshot_exists(mssql_database, snapshot.market_snapshot_id)


def test_exception_rolls_back_the_whole_graph(mssql_database: TemporaryMssqlDatabase) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    candidate = new_candidate(snapshot.market_snapshot_id)

    with pytest.raises(RuntimeError, match="stop"), factory() as uow:
        uow.market_snapshots.add(snapshot)
        uow.candidates.add(candidate)
        raise RuntimeError("stop")

    assert not _snapshot_exists(mssql_database, snapshot.market_snapshot_id)


def test_explicit_rollback_removes_the_whole_graph(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    candidate = new_candidate(snapshot.market_snapshot_id)
    evaluation = new_evaluation(candidate.candidate_id)

    with factory() as uow:
        uow.market_snapshots.add(snapshot)
        uow.candidates.add(candidate)
        uow.filter_evaluations.add(evaluation)
        uow.rollback()

    assert not _snapshot_exists(mssql_database, snapshot.market_snapshot_id)


def test_duplicate_failure_rolls_back_earlier_insert(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    duplicate = replace(snapshot, market_snapshot_id=MarketSnapshotID(uuid4()))

    with pytest.raises(DuplicateRecordError), factory() as uow:
        uow.market_snapshots.add(snapshot)
        uow.market_snapshots.add(duplicate)

    assert not _snapshot_exists(mssql_database, snapshot.market_snapshot_id)


def test_fk_failure_rolls_back_earlier_insert(mssql_database: TemporaryMssqlDatabase) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    invalid_candidate = new_candidate(MarketSnapshotID(uuid4()))

    with pytest.raises(ForeignKeyViolationError), factory() as uow:
        uow.market_snapshots.add(snapshot)
        uow.candidates.add(invalid_candidate)

    assert not _snapshot_exists(mssql_database, snapshot.market_snapshot_id)
