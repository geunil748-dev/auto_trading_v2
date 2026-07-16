"""Real MSSQL duplicate-race and unrelated-constraint behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from threading import Barrier, Lock
from types import TracebackType

import pytest
from sqlalchemy import select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDecisionIDFactory
from auto_trading_v2.adapters.persistence.tables import strategy_decisions
from auto_trading_v2.adapters.persistence.unit_of_work import (
    SqlAlchemyUnitOfWork,
    SqlAlchemyUnitOfWorkFactory,
)
from auto_trading_v2.application.contracts.position_exit_decisions import (
    PositionExitDecisionOutcome,
    PositionExitDecisionResult,
)
from auto_trading_v2.application.position_exit_errors import (
    PositionExitPersistenceError,
)
from auto_trading_v2.application.services.position_exit_decision import (
    PositionExitDecisionService,
)
from auto_trading_v2.domain.primitives import DecisionID, MarketSnapshotID, PositionID
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.position_exit_decisions.helpers import (
    add_snapshot,
    decisions_for,
    prepare_position,
)

pytestmark = pytest.mark.integration


class _BarrierStrategyDecisionRepository:
    def __init__(self, delegate: object, barrier: Barrier) -> None:
        self._delegate = delegate
        self._barrier = barrier

    def get_by_position_snapshot_strategy(self, **values: object):
        result = self._delegate.get_by_position_snapshot_strategy(**values)  # type: ignore[attr-defined]
        self._barrier.wait(timeout=30)
        return result

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)


class _BarrierUnitOfWork:
    def __init__(self, delegate: SqlAlchemyUnitOfWork, barrier: Barrier) -> None:
        self._delegate = delegate
        self._barrier = barrier
        self.strategy_decisions: object

    def __enter__(self) -> _BarrierUnitOfWork:
        active = self._delegate.__enter__()
        self.strategy_decisions = _BarrierStrategyDecisionRepository(
            active.strategy_decisions,
            self._barrier,
        )
        return self

    def commit(self) -> None:
        self._delegate.commit()

    def rollback(self) -> None:
        self._delegate.rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._delegate.__exit__(exc_type, exc, traceback)

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)


class _RacingUnitOfWorkFactory:
    def __init__(self, delegate: SqlAlchemyUnitOfWorkFactory) -> None:
        self._delegate = delegate
        self._barrier = Barrier(2)
        self._lock = Lock()
        self._created = 0

    def __call__(self):
        with self._lock:
            synchronize = self._created < 2
            self._created += 1
        unit_of_work = self._delegate()
        if synchronize:
            return _BarrierUnitOfWork(unit_of_work, self._barrier)
        return unit_of_work


@dataclass(frozen=True, slots=True)
class _FixedDecisionIDFactory:
    decision_id: DecisionID

    def new(self) -> DecisionID:
        return self.decision_id


def _run_racing_decision(
    factory: _RacingUnitOfWorkFactory,
    now: datetime,
    position_id: PositionID,
    snapshot_id: MarketSnapshotID,
) -> PositionExitDecisionResult:
    return PositionExitDecisionService(
        factory,  # type: ignore[arg-type]
        FixedClock(now),
        UuidDecisionIDFactory(),
    ).decide(position_id, snapshot_id)


def test_concurrent_semantic_duplicate_resolves_to_one_mssql_row(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="110",
    )
    factory = _RacingUnitOfWorkFactory(SqlAlchemyUnitOfWorkFactory(mssql_database.engine))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(
            executor.submit(
                _run_racing_decision,
                factory,
                observed_at,
                prepared.position.position_id,
                snapshot_id,
            )
            for _ in range(2)
        )
        results = tuple(future.result(timeout=60) for future in futures)

    assert {result.outcome for result in results} == {
        PositionExitDecisionOutcome.CREATED,
        PositionExitDecisionOutcome.ALREADY_DECIDED,
    }
    assert results[0].decision.decision_id == results[1].decision.decision_id
    assert decisions_for(mssql_database.engine, prepared.position.position_id) == (
        results[0].decision,
    )


def test_unrelated_mssql_duplicate_is_not_reported_as_already_decided(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="110",
    )
    with mssql_database.engine.connect() as connection:
        occupied_decision_id = DecisionID(
            connection.execute(
                select(strategy_decisions.c.decision_id).where(
                    strategy_decisions.c.candidate_id.is_not(None)
                )
            ).scalar_one()
        )
    exit_service = PositionExitDecisionService(
        SqlAlchemyUnitOfWorkFactory(mssql_database.engine),
        FixedClock(observed_at),
        _FixedDecisionIDFactory(occupied_decision_id),
    )

    with pytest.raises(PositionExitPersistenceError):
        exit_service.decide(prepared.position.position_id, snapshot_id)

    assert decisions_for(mssql_database.engine, prepared.position.position_id) == ()
