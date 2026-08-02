from __future__ import annotations

from typing import cast

import pytest

from auto_trading_v2.adapters.persistence.dotnet.connection import DotNetConnectionFactory
from auto_trading_v2.adapters.persistence.dotnet.core_adapter import DotNetCoreConnection
from auto_trading_v2.adapters.persistence.dotnet.unit_of_work import (
    DotNetUnitOfWork,
    DotNetUnitOfWorkFactory,
)
from auto_trading_v2.application.errors import TransactionStateError


class FakeRawTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.disposals = 0

    def Commit(self) -> None:
        self.commits += 1

    def Rollback(self) -> None:
        self.rollbacks += 1

    def Dispose(self) -> None:
        self.disposals += 1


class FakeConnection:
    def __init__(self) -> None:
        self.transaction = FakeRawTransaction()
        self.begins = 0
        self.closes = 0
        self.disposals = 0

    def BeginTransaction(self) -> FakeRawTransaction:
        self.begins += 1
        return self.transaction

    def Close(self) -> None:
        self.closes += 1

    def Dispose(self) -> None:
        self.disposals += 1


class FakeConnectionFactory:
    def __init__(self) -> None:
        self.opens = 0
        self.connections: list[FakeConnection] = []

    def open_connection(self) -> FakeConnection:
        self.opens += 1
        connection = FakeConnection()
        self.connections.append(connection)
        return connection


def _uow() -> tuple[DotNetUnitOfWork, FakeConnectionFactory]:
    factory = FakeConnectionFactory()
    return DotNetUnitOfWork(cast(DotNetConnectionFactory, factory)), factory


def test_factory_and_unit_of_work_are_lazy_until_context_entry() -> None:
    raw_factory = FakeConnectionFactory()
    factory = DotNetUnitOfWorkFactory(cast(DotNetConnectionFactory, raw_factory))

    uow = factory()

    assert raw_factory.opens == 0
    with uow:
        assert raw_factory.opens == 1
        assert raw_factory.connections[0].begins == 1


def test_seventeen_repositories_share_exactly_one_connection_and_transaction() -> None:
    uow, factory = _uow()

    with uow:
        repositories = (
            uow.daily_market_bars,
            uow.feature_snapshots,
            uow.universe_snapshots,
            uow.daily_feature_pipeline_runs,
            uow.daily_feature_scoring_runs,
            uow.daily_feature_outcomes,
            uow.daily_feature_outcome_observation_runs,
            uow.recommendations,
            uow.market_snapshots,
            uow.candidates,
            uow.filter_evaluations,
            uow.strategy_decisions,
            uow.trade_intents,
            uow.paper_orders,
            uow.paper_fills,
            uow.paper_positions,
            uow.position_events,
        )
        adapters = [
            cast(DotNetCoreConnection, repository._connection) for repository in repositories
        ]
        assert len(repositories) == 17
        assert len({id(adapter) for adapter in adapters}) == 1
        assert adapters[0].connection is factory.connections[0]
        assert adapters[0].transaction is factory.connections[0].transaction


def test_normal_exit_rolls_back_then_disposes_and_closes() -> None:
    uow, factory = _uow()

    with uow:
        assert uow.candidates is not None

    connection = factory.connections[0]
    assert connection.transaction.rollbacks == 1
    assert connection.transaction.commits == 0
    assert connection.transaction.disposals == 1
    assert connection.closes == 1
    assert connection.disposals == 1


def test_explicit_commit_is_one_shot_and_blocks_repository_access() -> None:
    uow, factory = _uow()

    with uow:
        uow.commit()
        with pytest.raises(TransactionStateError):
            _ = uow.candidates
        with pytest.raises(TransactionStateError):
            uow.commit()

    connection = factory.connections[0]
    assert connection.transaction.commits == 1
    assert connection.transaction.rollbacks == 0
    assert connection.transaction.disposals == 1


def test_repository_failure_marks_rollback_only_and_rejects_commit() -> None:
    uow, factory = _uow()

    with uow:
        uow.candidates._mark_failed()
        with pytest.raises(TransactionStateError, match="transaction_failed"):
            uow.commit()

    assert factory.connections[0].transaction.rollbacks == 1


def test_exception_exit_preserves_original_and_instance_reuse_is_forbidden() -> None:
    uow, factory = _uow()

    with pytest.raises(LookupError, match="original"), uow:
        raise LookupError("original")

    assert factory.connections[0].transaction.rollbacks == 1
    with pytest.raises(TransactionStateError, match="instance_reuse_forbidden"):
        uow.__enter__()
